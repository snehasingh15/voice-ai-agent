import json
import re
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from groq import Groq

from ..agent.prompts import SYSTEM_PROMPT, get_active_prompt
from ..agent.tools import (
    check_appointment_slots,
    create_booking,
    create_service_booking,
    initiate_outbound_call,
    list_doctors,
    retrieve_hospital_knowledge,
    update_booking,
    get_tool_definitions,
)
from ..agent_config import get_configured_llm
from ..config import GROQ_API_KEY, GEMINI_API_KEY, GROQ_MODELS as CONFIGURED_GROQ_MODELS, GEMINI_TEXT_MODELS


TOOL_PLACEHOLDER_PATTERN = re.compile(r"<function=(?P<name>[^>]+)>(?P<body>.*?)</function>", re.DOTALL)
LANGUAGE_CHOICE_PATTERN = re.compile(r"\b(hindi\s+or\s+english|english\s+or\s+hindi|continue\s+in\s+hindi|continue\s+in\s+english)\b", re.I)
DEVANAGARI_PATTERN = re.compile(r"[\u0900-\u097F]")
APPOINTMENT_INTENT_PATTERN = re.compile(r"\b(appointment|book|booking|doctor|consultation|slot|visit)\b", re.I)
ENGLISH_SIGNAL_PATTERN = re.compile(r"\b(hello|hi|i|want|need|book|appointment|doctor|please|english|yes|schedule)\b", re.I)
DECLARED_NAME_PATTERN = re.compile(r"\b(?:my full name is|my name is|patient(?:\\\'s|s)? name is|name is|i am|i\'m|im|this is|before as well,|before also,)\s+([A-Za-z][A-Za-z.\'-]*(?:\s+[A-Za-z][A-Za-z.\'-]*){0,3})", re.I)
FINAL_NAME_PATTERN = re.compile(r"\b([A-Za-z][A-Za-z.\'-]*(?:\s+[A-Za-z][A-Za-z.\'-]*){0,3})\s+is\s+the\s+final\s+name\b", re.I)
NAME_ADDRESS_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+ji\b")
NAME_CONFIRMATION_PATTERN = re.compile(r"\b(confirm|correct|spell|spelling|is that right|is this right|did i hear)\b", re.I)
AFFIRMATION_PATTERN = re.compile(r"^\s*(yes|yeah|yep|correct|right|confirm|confirmed|haan|han|ji|ok|okay)\s*[.!?]*\s*$", re.I)
AFFIRMATION_PREFIX_PATTERN = re.compile(r"^\s*(yes|yeah|yep|correct|right|confirm|confirmed|haan|han|ji|ok|okay)\b", re.I)
SPELLED_NAME_PATTERN = re.compile(r"\b(?:[a-zA-Z]\s+){2,}[a-zA-Z]\b")
LAST_NAME_CONFIRMATION_PATTERN = re.compile(r"(?:patient(?:'s|s)? name as|name i have is)\s+[\"?]?([A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){0,3})(?=\s*(?:[.?!,\"?]|is that|if not|$))", re.I)
AGE_PATTERN = re.compile(r"\b(?:age\s*(?:is)?\s*)?(?:1[0-1]\d|[1-9]\d?)\b", re.I)
GENDER_PATTERN = re.compile(r"\b(male|female|man|woman|boy|girl|other|trans|transgender)\b", re.I)
DATE_PATTERN = re.compile(r"\b(20\d{2}-\d{2}-\d{2}|today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december))\b", re.I)
TIME_PATTERN = re.compile(r"\b([01]?\d|2[0-3])(?::[0-5]\d)?\s*(am|pm)?\b", re.I)
DEPARTMENT_OR_DOCTOR_PATTERN = re.compile(r"\b(dr\.?|doctor|department|medicine|cardiology|neurology|urology|pulmonology|rheumatology|pain|fever|cough|heart|kidney|stomach|child|paediatric|physio|oncology|fertility|ivf)\b", re.I)
DOCTOR_CONFIRMATION_PATTERN = re.compile(r"book with\s+(Dr\.\s+[A-Za-z]+(?:\s+[A-Za-z]+){0,2}),?\s+correct", re.I)
WEEKDAY_PATTERN = re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)
DOCTOR_ARPIT_PATTERN = re.compile(r"\b(arpit|arpid|arpidjan|arpit\s*jain|arpid\s*jain|pijan|pijain|pee\s*jain|ar\s*pit|arpi\w*)\b", re.I)
DOCTOR_SEEMA_PATTERN = re.compile(r"\b(seema\s*dhir|seemadhir|seema\s*deer|simadeer|sima\s*deer|seema)\b", re.I)
PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
HEALTH_DEPARTMENT_MAP = [
    (re.compile(r"\b(stomach|ache|fever|general|body pain|medicine)\b", re.I), "Internal Medicine"),
    (re.compile(r"\b(heart|cardio|cardiac)\b", re.I), "Paediatric Cardiology"),
    (re.compile(r"\b(kidney|urine|urinary|stone)\b", re.I), "Urology"),
    (re.compile(r"\b(cough|breathing|lungs)\b", re.I), "Pulmonology"),
]
WEEKDAY_PATTERN = re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)
MONTH_NAMES = {
    "01": "January", "02": "February", "03": "March", "04": "April", "05": "May", "06": "June",
    "07": "July", "08": "August", "09": "September", "10": "October", "11": "November", "12": "December",
}


def _sanitize_agent_reply(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    text = re.sub(r"\((?:[^)]*(?:e\.g\.|example|for example|provide a date)[^)]*)\)", "", text, flags=re.I)
    text = re.sub(r"\be\.g\.,-\s*", "for example ", text, flags=re.I)
    text = re.sub(r"\bi\.e\.,-\s*", "that is ", text, flags=re.I)

    def replace_iso_date(match: re.Match[str]) -> str:
        year, month, day = match.group(1), match.group(2), match.group(3)
        month_name = MONTH_NAMES.get(month, month)
        return f"{month_name} {int(day)}, {year}"

    text = re.sub(r"\b(20\d{2})-(\d{2})-(\d{2})\b", replace_iso_date, text)
    text = text.replace("\u202f", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _has_appointment_intent(text: str) -> bool:
    return bool(APPOINTMENT_INTENT_PATTERN.search(text or ""))


def _looks_english(text: str) -> bool:
    text = text or ""
    if DEVANAGARI_PATTERN.search(text):
        return False
    return bool(ENGLISH_SIGNAL_PATTERN.search(text))


def _booking_next_question(user_text: str, history: list[dict[str, str]]) -> str:
    text = _user_conversation_text(user_text, history).lower()
    confirmed_name = _last_confirmed_name(history, user_text)
    declared_name = _extract_declared_name(text)
    if not DEPARTMENT_OR_DOCTOR_PATTERN.search(text):
        return "I can help book that. Which doctor, department, or health concern is the appointment for?"
    if not confirmed_name and not declared_name:
        return "Could you please tell me the patient's full name?"
    if declared_name and not confirmed_name:
        return _name_confirmation_reply(declared_name)
    if not AGE_PATTERN.search(text):
        return "Could you please tell me the patient's age?"
    if not GENDER_PATTERN.search(text):
        return "Could you please tell me the patient's gender?"
    if not DATE_PATTERN.search(text):
        return "What date would you prefer for the appointment?"
    if not TIME_PATTERN.search(text):
        return "What time between 10 AM and 4 PM would you prefer?"
    return "Please confirm these details, and I will create the appointment request."

def _extract_spelled_name(text: str) -> str:
    match = SPELLED_NAME_PATTERN.search(text or "")
    if not match:
        return ""
    letters = re.findall(r"[A-Za-z]", match.group(0))
    if len(letters) < 3 or len(letters) > 24:
        return ""
    return "".join(letters).capitalize()


def _extract_final_name(text: str) -> str:
    match = FINAL_NAME_PATTERN.search(text or "")
    if not match:
        return ""
    name = re.sub(r"\s+", " ", match.group(1)).strip(" .,\'-\t\n\r")
    return " ".join(part[:1].upper() + part[1:].lower() for part in name.split()[:4])


def _extract_declared_name(text: str) -> str:
    final_name = _extract_final_name(text)
    if final_name:
        return final_name
    spelled_name = _extract_spelled_name(text)
    if spelled_name:
        return spelled_name
    match = DECLARED_NAME_PATTERN.search(text or "")
    if not match:
        return ""
    name = re.split(r"[.,!?]", match.group(1), maxsplit=1)[0]
    name = re.sub(r"\s+", " ", name).strip(" .,'-\t\n\r")
    if not name or WEEKDAY_PATTERN.fullmatch(name.strip()) or DATE_PATTERN.fullmatch(name.strip()) or TIME_PATTERN.fullmatch(name.strip()):
        return ""
    stop_words = {"and", "for", "to", "with", "appointment", "doctor", "department", "age", "years", "year", "comma", "yes", "gender", "is"}
    parts = []
    for part in name.split():
        if part.lower() in stop_words or len(part) == 1:
            break
        parts.append(part[:1].upper() + part[1:].lower())
    cleaned = " ".join(parts[:4])
    if WEEKDAY_PATTERN.fullmatch(cleaned):
        return ""
    return cleaned
def _looks_like_person_name(text: str) -> str:
    value = re.sub(r"\s+", " ", text or "").strip(" .,!?\"'??\t\n\r")
    if not value:
        return ""
    if any(char.isdigit() for char in value):
        return ""
    if APPOINTMENT_INTENT_PATTERN.search(value) or DEPARTMENT_OR_DOCTOR_PATTERN.search(value):
        return ""
    words = value.split()
    if not 1 <= len(words) <= 4:
        return ""
    banned = {"yes", "no", "correct", "right", "confirm", "confirmed", "okay", "ok", "sure", "thanks", "thank", "you"}
    if any(word.lower() in banned for word in words):
        return ""
    if not all(re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", word) for word in words):
        return ""
    return " ".join(word[:1].upper() + word[1:].lower() for word in words)


def _assistant_asked_for_exact_name(history: list[dict[str, str]]) -> bool:
    for item in reversed(history[-4:]):
        if item.get("role") != "assistant":
            continue
        text = item.get("content", "").lower()
        if "full name exactly" in text or "spell the full name" in text or "patient's full name" in text or "patient?s full name" in text:
            return True
    return False


def _direct_confirmed_name(user_text: str, history: list[dict[str, str]]) -> str:
    final_name = _extract_final_name(user_text)
    if final_name:
        return final_name
    if _assistant_asked_for_exact_name(history):
        return _looks_like_person_name(user_text)
    return ""

def _name_was_recently_confirmed(history: list[dict[str, str]], declared_name: str) -> bool:
    if not declared_name:
        return False
    target = declared_name.lower()
    for item in history[-8:]:
        text = item.get("content", "").lower()
        if item.get("role") == "user" and target in text and any(word in text for word in ["yes", "correct", "right", "confirm", "confirmed"]):
            return True
    return False


def _name_confirmation_reply(name: str) -> str:
    if not name:
        return "I want to capture the name correctly. Could you please say or spell the patient's full name once more?"
    return f"I heard the patient's name as {name}. Is that correct? If not, please spell it for me."

def _conversation_text(user_text: str, history: list[dict[str, str]]) -> str:
    return "\n".join([item.get("content", "") for item in history[-14:]] + [user_text or ""])

def _user_conversation_text(user_text: str, history: list[dict[str, str]]) -> str:
    return "\n".join([item.get("content", "") for item in history[-14:] if item.get("role") == "user"] + [user_text or ""])

def _extract_age(text: str) -> str:
    match = re.search(r"\bage\s*(?:is)?\s*(1[0-1]\d|[1-9]\d?)\b|\b(1[0-1]\d|[1-9]\d?)\s*(?:years? old|yrs? old)\b", text or "", re.I)
    return next((group for group in match.groups() if group), "") if match else ""


def _extract_gender(text: str) -> str:
    match = GENDER_PATTERN.search(text or "")
    if not match:
        return ""
    value = match.group(1).lower()
    return {"man": "male", "boy": "male", "woman": "female", "girl": "female", "transgender": "trans"}.get(value, value)


def _extract_phone(text: str) -> str:
    match = PHONE_PATTERN.search(text or "")
    if not match:
        return ""
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) < 8:
        return ""
    return digits


def _next_weekday_date(weekday_name: str) -> str:
    weekdays = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    target = weekdays.get((weekday_name or "").lower())
    if target is None:
        return ""
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return (today + timedelta(days=days_ahead)).isoformat()


def _extract_date(text: str) -> str:
    iso = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text or "")
    if iso:
        return iso.group(0)
    weekday = WEEKDAY_PATTERN.search(text or "")
    if weekday:
        return _next_weekday_date(weekday.group(1))
    match = DATE_PATTERN.search(text or "")
    return match.group(1) if match else ""


def _extract_time(text: str) -> str:
    spoken = re.search(r"\b([01]?\d|2[0-3])\s*(?:thirty|30)\b", text or "", re.I)
    if spoken:
        return f"{int(spoken.group(1)):02d}:30"
    matches = list(TIME_PATTERN.finditer(text or ""))
    if not matches:
        return ""
    match = matches[-1]
    hour = int(match.group(1))
    meridiem = (match.group(2) or "").lower()
    minute_match = re.search(r":([0-5]\d)", match.group(0))
    minute = minute_match.group(1) if minute_match else "00"
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def _extract_department(text: str) -> str:
    text = text or ""
    if re.search(r"\binternal\s+medicine\b|\bmedicine\b", text, re.I):
        return "Internal Medicine"
    for pattern, department in HEALTH_DEPARTMENT_MAP:
        if pattern.search(text):
            return department
    return ""


def _extract_doctor(text: str) -> str:
    text = text or ""
    if DOCTOR_SEEMA_PATTERN.search(text):
        return "Dr. Seema Dhir"
    if DOCTOR_ARPIT_PATTERN.search(text):
        return "Dr. Arpit Jain"
    match = re.search(r"\b(?:dr\.?|doctor)\s+([A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){0,2})", text, re.I)
    if not match:
        return ""
    name = re.sub(r"\s+", " ", match.group(1)).strip(" .,'-\t\n\r")
    return f"Dr. {' '.join(part[:1].upper() + part[1:].lower() for part in name.split())}" if name else ""


def _last_assistant_doctor(history: list[dict[str, str]]) -> str:
    for item in reversed(history[-8:]):
        if item.get("role") != "assistant":
            continue
        doctor = _extract_doctor(item.get("content", ""))
        if doctor:
            return doctor
    return ""


def _confirmed_doctor_from_history(history: list[dict[str, str]], user_text: str) -> str:
    for index, item in enumerate(history[-12:]):
        if item.get("role") != "assistant":
            continue
        match = DOCTOR_CONFIRMATION_PATTERN.search(item.get("content", ""))
        if not match:
            continue
        for answer in history[-12:][index + 1:] + [{"role": "user", "content": user_text or ""}]:
            if answer.get("role") == "user" and AFFIRMATION_PREFIX_PATTERN.match(answer.get("content", "")):
                return match.group(1).strip()
    return ""


def _extract_booking_state(user_text: str, history: list[dict[str, str]]) -> dict[str, str]:
    text = _user_conversation_text(user_text, history)
    explicit_doctor = _extract_doctor(text)
    state = {
        "patient_name": _direct_confirmed_name(user_text, history) or _last_confirmed_name(history, user_text),
        "age": _extract_age(text),
        "gender": _extract_gender(text),
        "doctor_name": explicit_doctor or _confirmed_doctor_from_history(history, user_text) or _last_assistant_doctor(history),
        "department": _extract_department(text),
        "appointment_date": _extract_date(text),
        "appointment_time": _extract_time(text),
        "phone": _extract_phone(text),
    }
    return {key: value for key, value in state.items() if value}


def _merge_booking_arguments(arguments: dict[str, Any], user_text: str, history: list[dict[str, str]]) -> dict[str, Any]:
    merged = dict(arguments or {})
    for key, value in _extract_booking_state(user_text, history).items():
        merged[key] = value
    return merged

def _last_name_confirmation(history: list[dict[str, str]]) -> str:
    for item in reversed(history[-8:]):
        if item.get("role") != "assistant":
            continue
        match = LAST_NAME_CONFIRMATION_PATTERN.search(item.get("content", ""))
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip(" .,'-\t\n\r")
    return ""


def _last_confirmed_name(history: list[dict[str, str]], user_text: str) -> str:
    current_final_name = _direct_confirmed_name(user_text, history)
    if current_final_name:
        return current_final_name
    for item in reversed(history[-12:]):
        if item.get("role") == "user":
            historical_final_name = _extract_final_name(item.get("content", ""))
            if historical_final_name:
                return historical_final_name
    pending_name = _last_name_confirmation(history)
    if pending_name and AFFIRMATION_PREFIX_PATTERN.match(user_text or ""):
        return pending_name
    for index, item in enumerate(history[-12:]):
        if item.get("role") != "assistant":
            continue
        match = LAST_NAME_CONFIRMATION_PATTERN.search(item.get("content", ""))
        if not match:
            continue
        name = re.sub(r"\s+", " ", match.group(1)).strip(" .,'-\t\n\r")
        for answer in history[-12:][index + 1:]:
            if answer.get("role") == "user" and AFFIRMATION_PREFIX_PATTERN.match(answer.get("content", "")):
                return name
    return ""


def _has_booking_context(user_text: str, history: list[dict[str, str]]) -> bool:
    combined = _conversation_text(user_text, history).lower()
    return bool(APPOINTMENT_INTENT_PATTERN.search(combined) or DEPARTMENT_OR_DOCTOR_PATTERN.search(combined) or "patient's name" in combined or "patient name" in combined)


def _has_confirmed_patient_name(name: str, user_text: str, history: list[dict[str, str]]) -> bool:
    name = re.sub(r"\s+", " ", name or "").strip().lower()
    if not name or name in {"unknown", "anonymous"}:
        return False
    if _last_confirmed_name(history, user_text).lower() == name:
        return True
    if _direct_confirmed_name(user_text, history).lower() == name:
        return True
    if _extract_declared_name(user_text).lower() == name:
        return False
    for index, item in enumerate(history[-12:]):
        if item.get("role") != "assistant":
            continue
        assistant_text = item.get("content", "").lower()
        if name in assistant_text and NAME_CONFIRMATION_PATTERN.search(assistant_text):
            for answer in history[-12:][index + 1:]:
                if answer.get("role") == "user" and AFFIRMATION_PREFIX_PATTERN.match(answer.get("content", "")):
                    return True
    return False


def _missing_booking_fields(arguments: dict[str, Any], user_text: str, history: list[dict[str, str]]) -> list[str]:
    merged = _merge_booking_arguments(arguments, user_text, history)
    text = _user_conversation_text(user_text, history)
    missing: list[str] = []
    if not _has_confirmed_patient_name(str(merged.get("patient_name", "")), user_text, history):
        missing.append("confirmed patient name")
    if not str(merged.get("age", "")).strip():
        missing.append("age")
    if not str(merged.get("gender", "")).strip():
        missing.append("gender")
    if not (str(merged.get("doctor_name", "")).strip() or DEPARTMENT_OR_DOCTOR_PATTERN.search(text)):
        missing.append("doctor, department, or health concern")
    if not str(merged.get("appointment_date", "")).strip():
        missing.append("appointment date")
    if not str(merged.get("appointment_time", "")).strip():
        missing.append("appointment time")
    return missing


def _next_missing_field_question(missing: list[str]) -> str:
    if not missing:
        return "Please confirm the details before I create the appointment request."
    if missing[:2] == ["age", "gender"]:
        return "Could you please tell me the patient's age and gender?"
    field = missing[0]
    questions = {
        "confirmed patient name": "I need to confirm the patient's full name before booking. Please say yes if the name I read back is correct, or spell the full name.",
        "age": "Could you please tell me the patient's age?",
        "gender": "Could you please tell me the patient's gender?",
        "doctor, department, or health concern": "Which doctor, department, or health concern is the appointment for?",
        "appointment date": "What date would you prefer for the appointment?",
        "appointment time": "What time between 10 AM and 4 PM would you prefer?",
    }
    return questions.get(field, f"Could you please share the {field}?")


def _tool_block_result(reason: str, message: str, missing: list[str] | None = None) -> str:
    payload: dict[str, Any] = {"ok": False, "reason": reason, "message": message}
    if missing:
        payload["missing_fields"] = missing
    return json.dumps(payload, ensure_ascii=False)


def _format_spoken_date(value: Any) -> str:
    text = str(value or "").strip()
    match = re.fullmatch(r"(20\d{2})-(\d{2})-(\d{2})", text)
    if not match:
        return text
    year, month, day = match.groups()
    return f"{MONTH_NAMES.get(month, month)} {int(day)}, {year}"


def _spoken_booking_summary(state: dict[str, Any]) -> str:
    bits = []
    if state.get("patient_name"):
        bits.append(str(state["patient_name"]))
    if state.get("age"):
        bits.append(f"{state['age']} years old")
    if state.get("gender"):
        bits.append(str(state["gender"]))
    patient = ", ".join(bits) or "the patient"
    doctor = state.get("doctor_name") or state.get("department") or "the selected doctor"
    return f"{patient}, with {doctor}, on {_format_spoken_date(state.get('appointment_date'))} at {state.get('appointment_time')}"


def _booking_confirmation_reply(state: dict[str, Any]) -> str:
    return f"I have {_spoken_booking_summary(state)}. Please confirm once, and I will create the appointment request."


def _booking_ready_for_confirmation(user_text: str, history: list[dict[str, str]]) -> str:
    if not _has_booking_context(user_text, history):
        return ""
    state = _extract_booking_state(user_text, history)
    missing = _missing_booking_fields(state, user_text, history)
    if missing:
        if missing[0] == "confirmed patient name":
            declared_name = _extract_declared_name(user_text) or state.get("patient_name", "")
            if declared_name:
                return _name_confirmation_reply(str(declared_name))
        if missing == ["doctor, department, or health concern"] and state.get("department"):
            return ""
        if missing == ["doctor, department, or health concern"]:
            return "Which doctor, department, or health concern is the appointment for?"
        return _next_missing_field_question(missing)
    if not state.get("doctor_name") and state.get("department") == "Internal Medicine":
        return "For Internal Medicine, should I use Dr. Arpit Jain or Dr. Seema Dhir?"
    return _booking_confirmation_reply(state)


def _is_booking_confirmation_turn(user_text: str, history: list[dict[str, str]]) -> bool:
    latest_assistant = next((item.get("content", "") for item in reversed(history[-4:]) if item.get("role") == "assistant"), "")
    if not re.search(r"please confirm once|before i book|confirm the details|create the appointment request", latest_assistant, re.I):
        return False
    return bool(AFFIRMATION_PREFIX_PATTERN.match(user_text or "") or re.search(r"\b(book it|confirm it|go ahead|please book|quickly book|create it)\b", user_text or "", re.I))


def _booking_created_reply(tool_output: str) -> str:
    try:
        payload = json.loads(tool_output or "{}")
    except Exception:
        payload = {}
    if payload.get("ok") and payload.get("booking"):
        booking = payload["booking"]
        replay_note = " It was already registered, so I did not create a duplicate." if payload.get("idempotent_replay") else ""
        return f"Sure, your booking is confirmed on the dashboard for {booking.get('patient_name', 'the patient')} on {_format_spoken_date(booking.get('appointment_date'))} at {booking.get('appointment_time')}.{replay_note}"
    if payload.get("reason") == "slot_already_booked":
        return "That slot has just been booked by someone else. Please choose another time between 10 AM and 4 PM."
    if payload.get("message"):
        return payload["message"]
    return "I could not create the booking yet. Please confirm the appointment details once more."


def _fallback_reply_from_tools(tool_results: list[dict[str, Any]], user_text: str, history: list[dict[str, str]]) -> str:
    if not tool_results:
        return _booking_next_question(user_text, history) if _has_appointment_intent(user_text) else "I can help with that. Could you please share a little more detail-"
    last = tool_results[-1]
    try:
        payload = json.loads(last.get("content") or "{}")
    except Exception:
        payload = {}
    reason = payload.get("reason")
    if reason == "booking_missing_fields":
        return _next_missing_field_question(payload.get("missing_fields") or [])
    if reason == "patient_name_confirmation_required":
        return payload.get("message") or "Please confirm or spell the patient's full name before I book it."
    if reason == "slot_already_booked":
        return "That slot is already booked. Please choose another time between 10 AM and 4 PM."
    if payload.get("ok") is True and payload.get("booking"):
        booking = payload["booking"]
        return f"The appointment request for {booking.get('patient_name', 'the patient')} on {_format_spoken_date(booking.get('appointment_date'))} at {booking.get('appointment_time')} has been registered."
    if "doctors" in payload:
        doctors = payload.get("doctors") or []
        if doctors:
            names = ", ".join([doc.get("doctorName", "") for doc in doctors[:3] if doc.get("doctorName")])
            return f"Available doctors include {names}. Which doctor would you prefer?"
        return "Which department or health concern is the appointment for?"
    if "available_slots" in payload:
        slots = payload.get("available_slots") or []
        if slots:
            state = _merge_booking_arguments(
                {
                    "doctor_name": (payload.get("doctor") or {}).get("doctorName", ""),
                    "department": payload.get("department", ""),
                    "appointment_date": payload.get("date", ""),
                },
                user_text,
                history,
            )
            requested_time = str(state.get("appointment_time", "")).strip()
            if requested_time and requested_time in slots:
                missing = _missing_booking_fields(state, user_text, history)
                if missing:
                    return _next_missing_field_question(missing)
                return _booking_confirmation_reply(state)
            if requested_time and requested_time not in slots:
                return f"{requested_time} is not available. Available slots include {', '.join(slots[:5])}. Which time should I use?"
            return f"Available slots include {', '.join(slots[:5])}. Which time should I use?"
        return "I do not see an available slot for that time. Please choose another time between 10 AM and 4 PM."
    return payload.get("message") or "I can continue. Please share the next appointment detail."


def _enforce_conversation_policy(reply_text: str, user_text: str, history: list[dict[str, str]]) -> str:
    reply_text = (reply_text or "").strip()
    user_text = user_text or ""
    direct_name = _direct_confirmed_name(user_text, history)
    if direct_name and _has_booking_context(user_text, history):
        state = _extract_booking_state(user_text, history)
        missing = _missing_booking_fields(state, user_text, history)
        return _next_missing_field_question(missing) if missing else _booking_confirmation_reply(state)
    declared_name = _extract_declared_name(user_text)
    final_name = _extract_final_name(user_text)
    if declared_name and not final_name and not _assistant_asked_for_exact_name(history) and not _name_was_recently_confirmed(history, declared_name):
        confirmed_in_reply = LAST_NAME_CONFIRMATION_PATTERN.search(reply_text)
        reply_name = confirmed_in_reply.group(1).strip() if confirmed_in_reply else ""
        addressed_names = [match.group(1).strip() for match in NAME_ADDRESS_PATTERN.finditer(reply_text)]
        if addressed_names or not NAME_CONFIRMATION_PATTERN.search(reply_text) or (reply_name and reply_name.lower() != declared_name.lower()):
            return _name_confirmation_reply(declared_name)
    if AFFIRMATION_PATTERN.match(user_text) and _last_name_confirmation(history):
        if LANGUAGE_CHOICE_PATTERN.search(reply_text) or DEVANAGARI_PATTERN.search(reply_text) or not reply_text:
            return _booking_next_question(user_text, history)
    if _has_booking_context(user_text, history) and re.search(r"\b(repeat|last detail|say that again|share the next appointment detail)\b", reply_text, re.I):
        return _booking_next_question(user_text, history)
    if _has_booking_context(user_text, history) and re.search(r"(confirm the following details|appointment for yourself|confirm the patient.?s age and gender|why are you asking)", reply_text, re.I):
        state = _extract_booking_state(user_text, history)
        missing = _missing_booking_fields(state, user_text, history)
        return _next_missing_field_question(missing) if missing else _booking_confirmation_reply(state)
    if _has_booking_context(user_text, history) and re.search(r"available slots include", reply_text, re.I):
        state = _extract_booking_state(user_text, history)
        if state.get("appointment_time"):
            missing = _missing_booking_fields(state, user_text, history)
            return _next_missing_field_question(missing) if missing else _booking_confirmation_reply(state)
    if _has_booking_context(user_text, history) and _looks_english(_conversation_text(user_text, history)) and LANGUAGE_CHOICE_PATTERN.search(reply_text):
        return _booking_next_question(user_text, history)
    if _has_booking_context(user_text, history) and _looks_english(_conversation_text(user_text, history)) and DEVANAGARI_PATTERN.search(reply_text):
        if LANGUAGE_CHOICE_PATTERN.search(reply_text):
            return _booking_next_question(user_text, history)
    return reply_text

GROQ_MODELS = [
    model.strip()
    for model in (CONFIGURED_GROQ_MODELS or "").split(",")
    if model.strip()
]

if not GROQ_MODELS:
    GROQ_MODELS = ["openai/gpt-oss-20b"]


def _call_groq_with_fallback(client: Groq, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, temperature: float = 0.2):
    """Try Groq models in fallback order until one succeeds."""
    configured = get_configured_llm()
    preferred_model = (configured.get("model") or "").strip()
    configured_temperature = configured.get("temperature", temperature)
    try:
        temperature = float(configured_temperature)
    except (TypeError, ValueError):
        pass

    model_names = [preferred_model] if preferred_model else []
    model_names.extend(model for model in GROQ_MODELS if model and model not in model_names)

    last_err = None
    for model_name in model_names:
        try:
            kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
            }
            max_tokens = configured.get("max_tokens")
            if max_tokens:
                kwargs["max_tokens"] = int(max_tokens)
            if tools:
                kwargs["tools"] = tools
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            err_str = str(exc)
            if "model_not_found" in err_str or "404" in err_str or "does not exist" in err_str:
                last_err = exc
                continue
            # For other non-404 errors, also try smaller/alternative model
            last_err = exc
            print(f"[llm][fallback] Model {model_name} failed: {exc}, trying next model...")
            continue
    raise last_err or RuntimeError("All Groq models failed.")


def _call_gemini_fallback(messages: list[dict[str, Any]]) -> str:
    """Fallback LLM generation using Google Gemini if Groq is unavailable."""
    if not GEMINI_API_KEY:
        return "I am experiencing high demand. Please try again shortly."
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        sys_prompt = next((m["content"] for m in messages if m.get("role") == "system"), SYSTEM_PROMPT)
        chat_contents = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages if m.get("role") != "system"]
        prompt_text = f"System Instructions: {sys_prompt}\n\nConversation:\n" + "\n".join(chat_contents)
        
        fallback_models = [
            model.replace("models/", "").strip()
            for model in (GEMINI_TEXT_MODELS or "").split(",")
            if model.strip()
        ] or ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"]
        for m_name in fallback_models:
            try:
                resp = client.models.generate_content(model=m_name, contents=prompt_text, config={"automatic_function_calling": {"disable": True}})
                if resp and resp.text:
                    return resp.text
            except Exception:
                continue
    except Exception as exc:
        print(f"[llm][gemini-fallback] failed: {exc}")
    return "I am here to help. Please share your request or preferred time."


def _call_tool_function(
    tool_name: str,
    arguments: dict[str, Any],
    event_callback: Any | None = None,
    used_tools: list[str] | None = None,
    user_text: str = "",
    history: list[dict[str, str]] | None = None,
) -> str:
    print(f"[tool-call] {tool_name} args={arguments}")
    if used_tools is not None:
        used_tools.append(tool_name)
    if event_callback:
        try:
            res = event_callback({"tool": tool_name, "args": arguments, "status": "called"})
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)
        except Exception as e:
            print(f"[tool-event-callback] scheduling error: {e}")
    if tool_name == "list_doctors":
        evidence = _user_conversation_text(user_text, history or [])
        department = arguments.get("department") or ""
        health_issue = arguments.get("health_issue") or ""
        if not (department or health_issue) or not DEPARTMENT_OR_DOCTOR_PATTERN.search(evidence):
            return _tool_block_result("booking_missing_fields", _next_missing_field_question(["doctor, department, or health concern"]), ["doctor, department, or health concern"])
        return list_doctors(department=department, health_issue=health_issue)
    if tool_name == "retrieve_hospital_knowledge":
        query = arguments.get("query", "")
        return retrieve_hospital_knowledge(query=query)
    if tool_name == "check_appointment_slots":
        evidence = _user_conversation_text(user_text, history or [])
        missing = []
        if not DEPARTMENT_OR_DOCTOR_PATTERN.search(evidence):
            missing.append("doctor, department, or health concern")
        if not DATE_PATTERN.search(evidence):
            missing.append("appointment date")
        if missing:
            return _tool_block_result("booking_missing_fields", _next_missing_field_question(missing), missing)
        merged = _merge_booking_arguments(arguments, user_text, history or [])
        doctor_name = merged.get("doctor_name", "")
        date = merged.get("date") or merged.get("appointment_date", "")
        department = merged.get("department", "")
        return check_appointment_slots(doctor_name=doctor_name, department=department, date=date)
    if tool_name == "create_booking":
        arguments = _merge_booking_arguments(arguments, user_text, history or [])
        missing = _missing_booking_fields(arguments, user_text, history or [])
        if missing:
            return _tool_block_result("booking_missing_fields", _next_missing_field_question(missing), missing)
        return create_booking(
            patient_name=arguments.get("patient_name", ""),
            age=arguments.get("age", ""),
            gender=arguments.get("gender", ""),
            doctor_name=arguments.get("doctor_name", ""),
            appointment_date=arguments.get("appointment_date", ""),
            appointment_time=arguments.get("appointment_time", ""),
            caller_id=arguments.get("caller_id") or "anonymous",
            department=arguments.get("department") or "",
            phone=arguments.get("phone") or "",
            notes=arguments.get("notes") or "",
            idempotency_key=arguments.get("idempotency_key") or "",
        )
    if tool_name == "create_service_booking":
        return create_service_booking(
            caller_id=arguments.get("caller_id") or "anonymous",
            customer_name=arguments.get("customer_name") or arguments.get("patient_name") or arguments.get("name") or "",
            service_type=arguments.get("service_type") or arguments.get("booking_type") or "callback",
            appointment_date=arguments.get("appointment_date") or arguments.get("date") or "",
            appointment_time=arguments.get("appointment_time") or arguments.get("time") or "",
            agent_id=arguments.get("agent_id") or "",
            industry=arguments.get("industry") or "",
            organization=arguments.get("organization") or "",
            phone=arguments.get("phone") or arguments.get("phone_number") or "",
            email=arguments.get("email") or "",
            notes=arguments.get("notes") or "",
            status=arguments.get("status") or "requested",
            idempotency_key=arguments.get("idempotency_key") or "",
        )
    if tool_name == "update_booking":
        return update_booking(
            booking_id=arguments.get("booking_id", ""),
            action=arguments.get("action", "confirm"),
            new_date=arguments.get("new_date"),
            new_time=arguments.get("new_time"),
            caller_id=arguments.get("caller_id"),
        )
    if tool_name == "initiate_outbound_call":
        return initiate_outbound_call(
            phone_number=arguments.get("phone_number", ""),
            caller_id=arguments.get("caller_id"),
        )
    return json.dumps({"error": f"unknown tool: {tool_name}"})


def _parse_raw_tool_call_from_text(text: str) -> tuple[str, dict[str, Any]] | None:
    match = TOOL_PLACEHOLDER_PATTERN.search(text)
    if not match:
        return None

    tool_name = match.group("name").strip()
    raw_body = match.group("body").strip()
    if not raw_body:
        return tool_name, {}

    try:
        return tool_name, json.loads(raw_body)
    except json.JSONDecodeError as exc:
        print(f"[llm][warning] could not parse raw tool arguments for {tool_name}: {exc}")
        return None


def _build_messages(
    user_text: str,
    history: list[dict[str, str]],
    tool_definitions: list[dict[str, Any]] | None = None,
    caller_summary: str | None = None,
    custom_system_prompt: str | None = None,
    agent_context: str | None = None,
) -> list[dict[str, Any]]:
    active_prompt = custom_system_prompt or get_active_prompt()
    if agent_context:
        system_prompt = (
            "You are the selected live voice agent for this test session. Follow only the selected live agent context below, "
            "not any older active prompt/persona that may exist in the database. "
            "Do not mention unrelated brands, old demo agents, or previous personas unless the selected context says so. "
            f"Selected live agent context: {agent_context} "
        )
    else:
        system_prompt = active_prompt
    if caller_summary:
        system_prompt = (
            f"{system_prompt} Previous caller memory, for context only: {caller_summary} "
            "If this is the first user turn of a new session, briefly acknowledge the returning caller and offer to continue the prior unresolved task, but only after answering their latest request. "
            "Do not use remembered names, doctors, dates, times, age, gender, or booking details as current appointment fields unless the caller explicitly states or confirms them in this call. "
            "If the current caller gives a name, use exactly the current spoken name and ask confirmation before booking."
        )
    uploaded_context = [
        item.get("content", "")
        for item in history
        if "I analyzed the uploaded" in item.get("content", "")
    ]
    if uploaded_context:
        system_prompt += (
            " Recent uploaded file context is available below. "
            "When the caller asks about an uploaded image or file, answer directly from this context. "
            "Do not say you cannot view the image. Do not ask where it is stored. "
            "Do not create or mention a support ticket for image-description questions unless the caller explicitly asks for support. "
            "Uploaded file context: " + " | ".join(uploaded_context[-3:])
        )
    system_prompt += (
        " Conversation policy: detect language from meaningful caller speech. "
        "If the caller already speaks in English, continue in English and do not ask Hindi or English. "
        "If the selected context is healthcare and the caller asks to book an appointment, continue by asking for doctor, department, health concern, date, or time as needed. "
        "Do not restart the greeting after an interruption, silence, FAQ, or language switch. "
        "For non-healthcare selected agents, never use medical-role wording unless the selected agent context explicitly says healthcare. Use student, caller, customer, client, traveller, or user wording according to the selected agent context. "
        "Voice replies must be spoken naturally: do not say e.g., raw ISO dates, markdown, parentheses, examples, or internal identifiers. "
        "When a tool is needed, do not embed raw function syntax in the reply. "
        "Instead, use the model's tool-calling interface so tool calls are handled by the API."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for item in history:
        messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": user_text})
    return messages



def _agent_context_is_healthcare(agent_context: str | None) -> bool:
    if not agent_context:
        return True
    lowered = agent_context.lower()
    return "industry: healthcare" in lowered or "patient assistant" in lowered or "apollo health" in lowered

def _non_healthcare_patient_leak(reply: str, agent_context: str | None) -> bool:
    if _agent_context_is_healthcare(agent_context):
        return False
    return bool(re.search(r"\b(patient|doctor|hospital|health concern|department)\b", reply or "", re.I))


def _selected_agent_repair_reply(user_text: str, agent_context: str | None) -> str:
    lowered = (agent_context or "").lower()
    if "industry: education" in lowered:
        return "Hi Priya. This is the FORE School counsellor agent. I can explain the programme, answer admissions questions, and book a counsellor discussion. What date and time would you prefer for the counselling booking?"
    if "industry: finance" in lowered:
        return "I can help with your finance or consultancy request and book a consultation. What topic should the consultation cover, and what date and time work for you?"
    if "industry: travel" in lowered:
        return "I can help plan your travel enquiry and book a travel consultation. Which destination and date should I note?"
    if "industry: telecom" in lowered:
        return "I can help with your support request and book a callback if needed. What issue should I note?"
    return "I can help with that agent's service booking. What date and time should I note?"
def generate_agent_reply(
    user_text: str,
    history: list[dict[str, str]],
    tool_definitions: list[dict[str, Any]] | None = None,
    client: Any | None = None,
    event_callback: Any | None = None,
    caller_summary: str | None = None,
    used_tools: list[str] | None = None,
    caller_id: str = "anonymous",
    agent_context: str | None = None,
) -> str:
    """Call Groq with model fallback and tool calling support; fallback to Gemini if needed."""
    healthcare_booking_shortcuts = _agent_context_is_healthcare(agent_context)
    if healthcare_booking_shortcuts and _is_booking_confirmation_turn(user_text, history):
        state = _extract_booking_state(user_text, history)
        missing = _missing_booking_fields(state, user_text, history)
        if missing:
            return _next_missing_field_question(missing)
        tool_output = _call_tool_function(
            "create_booking",
            {**state, "caller_id": caller_id or "anonymous"},
            event_callback=event_callback,
            used_tools=used_tools,
            user_text=user_text,
            history=history,
        )
        return _booking_created_reply(tool_output)
    deterministic_booking_reply = _booking_ready_for_confirmation(user_text, history) if healthcare_booking_shortcuts else ""
    if deterministic_booking_reply:
        return deterministic_booking_reply

    if client is None:
        api_key = GROQ_API_KEY
        if not api_key:
            messages = _build_messages(user_text, history, tool_definitions, caller_summary=caller_summary, agent_context=agent_context)
            return _call_gemini_fallback(messages)
        client = Groq(api_key=api_key)

    if tool_definitions is None:
        tool_definitions = get_tool_definitions()

    messages = _build_messages(user_text, history, tool_definitions, caller_summary=caller_summary, agent_context=agent_context)

    try:
        response = _call_groq_with_fallback(client, messages, tools=tool_definitions, temperature=0.2)
    except Exception as exc:
        print(f"[llm][warning] Groq failed ({exc}), attempting Gemini fallback...")
        return _call_gemini_fallback(messages)

    message = response.choices[0].message
    reply_text = getattr(message, "content", "") or ""
    if _non_healthcare_patient_leak(reply_text, agent_context):
        return _selected_agent_repair_reply(user_text, agent_context)
    tool_calls = getattr(message, "tool_calls", None) or []

    if not tool_calls and "<function=" in reply_text:
        print(f"[llm][warning] reply contains raw tool placeholder text: {reply_text}")
        parsed = _parse_raw_tool_call_from_text(reply_text)
        if parsed:
            function_name, arguments = parsed
            tool_output = _call_tool_function(function_name, arguments, event_callback=event_callback, used_tools=used_tools, user_text=user_text, history=history)
            follow_up_messages = list(messages)
            follow_up_messages.append({
                "role": "assistant",
                "content": "I'm using the requested tool.",
                "tool_calls": [
                    {
                        "id": "tool-1",
                        "type": "function",
                        "function": {"name": function_name, "arguments": json.dumps(arguments)},
                    }
                ],
            })
            follow_up_messages.append({"role": "tool", "content": tool_output})
            try:
                follow_up_response = _call_groq_with_fallback(client, follow_up_messages, tools=tool_definitions, temperature=0.2)
                follow_up_message = follow_up_response.choices[0].message
                final_reply = getattr(follow_up_message, "content", "") or ""
                if "<function=" in final_reply:
                    final_reply = _enforce_conversation_policy(final_reply.replace("<function=", "[tool-call]"), user_text, history)
                    if _non_healthcare_patient_leak(final_reply, agent_context):
                        return _selected_agent_repair_reply(user_text, agent_context)
                    return final_reply
                final_reply = _enforce_conversation_policy(final_reply, user_text, history)
                if _non_healthcare_patient_leak(final_reply, agent_context):
                    return _selected_agent_repair_reply(user_text, agent_context)
                return final_reply or _fallback_reply_from_tools([{"role": "tool", "content": tool_output}], user_text, history)
            except Exception:
                return "The requested information has been updated."

    if tool_calls:
        tool_results: list[dict[str, Any]] = []
        serialized_tool_calls = []
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except Exception:
                arguments = {}
            serialized_tool_calls.append(
                {
                    "id": getattr(tool_call, "id", "tool-1"),
                    "type": "function",
                    "function": {"name": function_name, "arguments": tool_call.function.arguments or "{}"},
                }
            )
            tool_output = _call_tool_function(function_name, arguments, event_callback=event_callback, used_tools=used_tools, user_text=user_text, history=history)
            tool_results.append({"tool_call_id": getattr(tool_call, "id", "tool-1"), "role": "tool", "content": tool_output})

        follow_up_messages = list(messages)
        follow_up_messages.append({"role": "assistant", "content": "I'm using the requested tool.", "tool_calls": serialized_tool_calls})
        follow_up_messages.extend(tool_results)
        try:
            follow_up_response = _call_groq_with_fallback(client, follow_up_messages, tools=tool_definitions, temperature=0.2)
            follow_up_message = follow_up_response.choices[0].message
            final_reply = getattr(follow_up_message, "content", "") or ""
            if "<function=" in final_reply:
                final_reply = _enforce_conversation_policy(final_reply.replace("<function=", "[tool-call]"), user_text, history)
                if _non_healthcare_patient_leak(final_reply, agent_context):
                    return _selected_agent_repair_reply(user_text, agent_context)
                return final_reply
            final_reply = _enforce_conversation_policy(final_reply, user_text, history)
            if _non_healthcare_patient_leak(final_reply, agent_context):
                return _selected_agent_repair_reply(user_text, agent_context)
            return final_reply or _fallback_reply_from_tools(tool_results, user_text, history)
        except Exception:
            return "I have processed your request."

    reply_text = _enforce_conversation_policy(reply_text, user_text, history)
    if _non_healthcare_patient_leak(reply_text, agent_context):
        return _selected_agent_repair_reply(user_text, agent_context)
    return reply_text or (_booking_next_question(user_text, history) if healthcare_booking_shortcuts and _has_appointment_intent(user_text) else "I can help with that. Could you please repeat the last detail-")


def summarize_conversation(history: list[dict[str, str]]) -> str:
    if not history:
        return ""

    conversation_lines = []
    for item in history:
        role = item.get("role", "unknown")
        content = item.get("content", "")
        if role == "user":
            conversation_lines.append(f"Caller: {content}")
        elif role == "assistant":
            conversation_lines.append(f"Assistant: {content}")
        else:
            conversation_lines.append(f"{role.capitalize()}: {content}")

    messages = [
        {
            "role": "system",
            "content": "You are a concise summarization assistant."
        },
        {
            "role": "user",
            "content": (
                "Summarize the key facts about this caller and what they discussed, "
                "in 2-3 sentences, for future reference.\n\n"
                "Conversation:\n"
                + "\n".join(conversation_lines)
            ),
        },
    ]

    api_key = GROQ_API_KEY
    if not api_key:
        return _call_gemini_fallback(messages)
    try:
        client = Groq(api_key=api_key)
        response = _call_groq_with_fallback(client, messages, temperature=0.2)
        return getattr(response.choices[0].message, "content", "") or ""
    except Exception:
        return _call_gemini_fallback(messages)





