"""Read full toast XML (launch/actions/tag) via ToastNotificationManager.history.

UserNotificationListener only exposes the visual binding (title/body).
The activation payload and Electron toast tag live in each app's toast history.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from winsdk.windows.ui.notifications import KnownNotificationBindings, ToastNotificationManager


def _local_name(tag: str) -> str:
    if not tag:
        return ""
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _element_attr(elem, name: str) -> str:
    return (elem.get(name) or elem.get(name.lower()) or "").strip()


def _toast_texts(xml_text: str) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    texts = []
    for elem in root.iter():
        if _local_name(elem.tag) == "text" and elem.text:
            texts.append(elem.text.strip())
    return texts


def _parse_activation(xml_text: str) -> dict:
    info = {
        "raw_xml": xml_text,
        "launch": "",
        "launch_activation_type": "",
        "actions": [],
    }
    if not xml_text:
        return info

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return info

    info["launch"] = _element_attr(root, "launch")
    info["launch_activation_type"] = _element_attr(root, "activationType") or "foreground"

    for elem in root.iter():
        if _local_name(elem.tag) != "action":
            continue
        info["actions"].append({
            "content": _element_attr(elem, "content"),
            "arguments": _element_attr(elem, "arguments"),
            "activation_type": _element_attr(elem, "activationType") or "foreground",
        })

    return info


def _notification_texts(user_notification) -> list[str]:
    try:
        binding = user_notification.notification.visual.get_binding(
            KnownNotificationBindings.toast_generic
        )
        if binding is None:
            return []
        texts = binding.get_text_elements()
        return [texts.get_at(i).text.strip() for i in range(texts.size) if texts.get_at(i).text]
    except Exception:
        return []


def _history_xml(toast) -> str:
    try:
        content = toast.content
        if content is None:
            return ""
        root = content.document_element
        if hasattr(root, "get_xml"):
            return root.get_xml() or ""
        if hasattr(root, "outer_xml"):
            value = root.outer_xml
            return value() if callable(value) else (value or "")
    except Exception:
        pass
    return ""


def _toast_tag_group(toast) -> tuple[str, str]:
    try:
        return (toast.tag or "").strip(), (toast.group or "").strip()
    except Exception:
        return "", ""


def _match_result(xml_text: str, toast) -> tuple[str, dict, str, str]:
    tag, group = _toast_tag_group(toast)
    return xml_text, _parse_activation(xml_text), tag, group


def find_toast_info(user_notification) -> tuple[str, dict, str, str]:
    """Return (xml, activation_info, toast_tag, toast_group) for a UserNotification."""
    aumid = ""
    try:
        if user_notification.app_info:
            aumid = user_notification.app_info.app_user_model_id or ""
    except Exception:
        pass
    if not aumid:
        return "", _parse_activation(""), "", ""

    try:
        history = ToastNotificationManager.history.get_history(aumid)
    except Exception:
        return "", _parse_activation(""), "", ""

    if history is None or history.size == 0:
        return "", _parse_activation(""), "", ""

    target_texts = _notification_texts(user_notification)
    best_toast = None
    best_xml = ""
    best_score = -1

    for i in range(history.size):
        toast = history.get_at(i)
        xml_text = _history_xml(toast)
        if not xml_text:
            continue
        candidate_texts = _toast_texts(xml_text)
        if target_texts and candidate_texts == target_texts:
            return _match_result(xml_text, toast)
        if target_texts and candidate_texts:
            overlap = len(set(target_texts) & set(candidate_texts))
            if overlap > best_score:
                best_score = overlap
                best_xml = xml_text
                best_toast = toast
        elif not best_xml:
            best_xml = xml_text
            best_toast = toast

    if best_toast is not None and best_xml:
        return _match_result(best_xml, best_toast)

    toast = history.get_at(history.size - 1)
    return _match_result(_history_xml(toast), toast)


def find_toast_xml(user_notification) -> tuple[str, dict]:
    xml_text, activation, _tag, _group = find_toast_info(user_notification)
    return xml_text, activation


def _is_electron_toast_args(value: str) -> bool:
    value = (value or "").strip().lower()
    return value.startswith("type=click") or value.startswith("type=reply") or value.startswith("type=action")


def _is_secondary_toast_action(arguments: str, label: str = "") -> bool:
    """True for toast button actions (reply, delete, etc.), not a body open click."""
    args = (arguments or "").lower()
    label = (label or "").strip().lower()
    for needle in (
        "action=reply",
        "action=delete",
        "action=flag",
        "action=dismiss",
        "action=snooze",
        "action=archive",
        "action=mark",
    ):
        if needle in args:
            return True
    return label in {
        "reply",
        "delete",
        "flag",
        "dismiss",
        "snooze",
        "archive",
        "mark as read",
    }


def _root_launch_target(activation_info: dict) -> dict:
    launch = activation_info.get("launch", "")
    if not launch or _is_electron_toast_args(launch):
        return {}
    activation_type = (activation_info.get("launch_activation_type") or "foreground").lower()
    if activation_type == "protocol" or "://" in launch:
        return {
            "kind": activation_type,
            "value": launch,
            "source": "launch",
            "label": "",
        }
    return {}


def best_launch_target(activation_info: dict) -> dict:
    """Pick the most useful protocol/deep-link target from parsed toast XML.

    A toast body click uses the root ``launch`` attribute (e.g. eM Client's
    ``em-toast:action=&...``). Button actions like Reply/Delete are only for
    those buttons — they must not win over the body open link.

    Ignores Electron COM reply/click argument strings — those are not URLs and
    are handled separately via toast_tag / app-specific activation (e.g. Beeper).
    """
    root = _root_launch_target(activation_info)
    if root:
        return root

    for action in activation_info.get("actions", []):
        args = action.get("arguments", "")
        activation_type = (action.get("activation_type") or "foreground").lower()
        label = action.get("content", "")
        if not args or _is_electron_toast_args(args):
            continue
        if _is_secondary_toast_action(args, label):
            continue
        if activation_type == "protocol" or "://" in args:
            return {
                "kind": activation_type,
                "value": args,
                "source": "action",
                "label": label,
            }

    for action in activation_info.get("actions", []):
        args = action.get("arguments", "")
        if args and not _is_electron_toast_args(args) and "://" in args:
            activation_type = (action.get("activation_type") or "foreground").lower()
            return {
                "kind": activation_type,
                "value": args,
                "source": "action",
                "label": action.get("content", ""),
            }

    launch = activation_info.get("launch", "")
    if launch and not _is_electron_toast_args(launch):
        activation_type = (activation_info.get("launch_activation_type") or "foreground").lower()
        return {
            "kind": activation_type,
            "value": launch,
            "source": "launch",
            "label": "",
        }

    return {"kind": "", "value": "", "source": "", "label": ""}
