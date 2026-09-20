"""Mongo-backed tools available to the healthcare voice agent.

The tools are deliberately deterministic and auditable so the LLM can take
real actions while MongoDB remains the source of truth for doctors, slots,
bookings, RAG retrieval, and telephony requests.
"""

from __future__ import annotations

import html
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, cast

import requests
from bson import ObjectId

from ..config import (
    EXOTEL_ACCOUNT_SID,
    EXOTEL_API_KEY,
    EXOTEL_API_BASE_URL,
    EXOTEL_API_TOKEN,
    EXOTEL_APP_URL,
    EXOTEL_CALLER_ID,
    EXOTEL_FLOW_URL,
    EXOTEL_STATUS_CALLBACK_URL,
    EXOTEL_STREAM_URL,
    PUBLIC_BASE_URL,
    TELEPHONY_PROVIDER,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER,
    TWILIO_STATUS_CALLBACK_URL,
    TWILIO_STREAM_URL,
    TWILIO_VOICE_URL,
)
from ..db.mongo import get_db
from ..rag.retriever import retrieve_relevant_chunks

DEFAULT_DOCTORS = [
    {"doctorName": "Dr. Arpit Jain", "doctorNameHindi": "डॉक्टर अर्पित जैन", "department": "Internal Medicine", "fee": "Rs 1500", "experience": "37 Years", "availability_text": "Monday to Saturday from 10 AM to 4 PM"},
    {"doctorName": "Dr. Seema Dhir", "doctorNameHindi": "डॉक्टर सीमा धीर", "department": "Internal Medicine", "fee": "Rs 1500", "experience": "32 Years", "availability_text": "Monday to Saturday from 10 AM to 4 PM"},
    {"doctorName": "Dr. Nidhi Rawal", "doctorNameHindi": "डॉक्टर निधि रावल", "department": "Paediatric Cardiology", "fee": "Rs 1400", "experience": "23 Years", "availability_text": "Monday to Saturday from 10 AM to 4 PM"},
    {"doctorName": "Dr. Ajit Singh Baghela", "doctorNameHindi": "डॉक्टर अजीत सिंह बाघेला", "department": "Paediatric Neurology", "fee": "Rs 1500", "experience": "12 Years", "availability_text": "Monday to Saturday from 10 AM to 4 PM"},
    {"doctorName": "Dr. Sidharth Kumar Sethi", "doctorNameHindi": "डॉक्टर सिद्धार्थ कुमार सेठी", "department": "Paediatric Nephrology", "fee": "Rs 1500", "experience": "15+ Years", "availability_text": "Monday to Saturday from 10 AM to 4 PM"},
    {"doctorName": "Dr. Shweta Bansal", "doctorNameHindi": "डॉक्टर श्वेता बंसल", "department": "Pulmonology", "fee": "Rs 1500", "experience": "12+ Years", "availability_text": "Monday to Saturday from 10 AM to 4 PM"},
    {"doctorName": "Dr. Ashu Kumar Jain", "doctorNameHindi": "डॉक्टर आशु कुमार जैन", "department": "Pain Medicine", "fee": "Rs 1400", "experience": "20+ Years", "availability_text": "Monday to Saturday from 10 AM to 4 PM"},
    {"doctorName": "Dr. Rajiv Yadav", "doctorNameHindi": "डॉक्टर राजीव यादव", "department": "Urology", "fee": "Rs 1600", "experience": "20+ Years", "availability_text": "Monday to Saturday from 10 AM to 4 PM"},
    {"doctorName": "Dr. Kiran Arora", "doctorNameHindi": "डॉक्टर किरण अरोड़ा", "department": "Reproductive Medicine", "fee": "Rs 2150", "experience": "20+ Years", "availability_text": "Monday to Saturday from 10 AM to 4 PM"},
    {"doctorName": "Dr. Sumeet Agrawal", "doctorNameHindi": "डॉक्टर सुमीत अग्रवाल", "department": "Rheumatology", "fee": "Rs 1950", "experience": "15+ Years", "availability_text": "Monday to Saturday from 10 AM to 4 PM"},
    {"doctorName": "Dr. Lalit Kumar", "doctorNameHindi": "डॉक्टर ललित कुमार", "department": "Medical Oncology", "fee": "Rs 1200", "experience": "30 Years", "availability_text": "Monday to Saturday from 10 AM to 4 PM"},
    {"doctorName": "Dr. Nalini Bajaj", "doctorNameHindi": "डॉक्टर नलिनी बजाज", "department": "NICU", "fee": "Rs 1600", "experience": "15+ Years", "availability_text": "Monday to Saturday from 10 AM to 4 PM"},
]

DEPARTMENT_KEYWORDS = {
    "Paediatric Neurology": ["neuro", "neurology", "brain", "seizure", "fits"],
    "Paediatric Cardiology": ["cardio", "heart", "cardiac", "dil"],
    "Paediatric Nephrology": ["kidney", "gurdha", "nephro"],
    "Pulmonology": ["lungs", "breathing", "saas", "pulmo", "cough"],
    "Rheumatology": ["joints", "arthritis", "rheum"],
    "Pain Medicine": ["pain", "dard", "chronic pain"],
    "Urology": ["urine", "urinary", "stone", "uro"],
    "NICU": ["newborn", "nicu", "premature"],
    "Medical Oncology": ["cancer", "tumour", "tumor", "onco"],
    "Reproductive Medicine": ["fertility", "ivf", "pregnancy difficulty"],
    "Internal Medicine": ["fever", "stomach", "general", "body pain", "medicine"],
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    return value


def _to_json(payload: Any) -> str:
    return json.dumps(_json_safe(payload), ensure_ascii=False)


def _doctors_collection():
    return get_db().get_collection("doctors")


def _bookings_collection():
    return get_db().get_collection("bookings")


def seed_default_doctors(force: bool = False) -> str:
    """Seed the doctors collection with a production demo roster."""
    coll = _doctors_collection()
    if force:
        coll.delete_many({})
    if coll.count_documents({}) == 0:
        now = datetime.now(timezone.utc)
        docs = []
        for item in DEFAULT_DOCTORS:
            docs.append({
                **item,
                "_id": str(uuid.uuid4()),
                "slot_start": "10:00",
                "slot_end": "16:00",
                "working_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
                "createdAt": now,
                "updatedAt": now,
            })
        coll.insert_many(docs)
    return _to_json({"ok": True, "doctor_count": coll.count_documents({})})


def list_doctors(department: str = "", health_issue: str = "") -> str:
    """Find doctors by department or health issue without hallucinating names."""
    seed_default_doctors(False)
    resolved_department = department.strip()
    issue = health_issue.lower().strip()
    if not resolved_department and issue:
        for dep, keywords in DEPARTMENT_KEYWORDS.items():
            if any(keyword in issue for keyword in keywords):
                resolved_department = dep
                break
    query = {"department": {"$regex": f"^{re.escape(resolved_department)}$", "$options": "i"}} if resolved_department else {}
    docs = list(_doctors_collection().find(query, {"embedding": 0}).sort("doctorName", 1).limit(8))
    return _to_json({"department": resolved_department or None, "doctors": docs})


def find_doctor(doctor_name: str) -> dict[str, Any] | None:
    seed_default_doctors(False)
    cleaned = re.sub(r"\bdr\.?\b", "", doctor_name or "", flags=re.I).strip()
    if not cleaned:
        return None
    escaped = re.escape(cleaned)
    return _doctors_collection().find_one({
        "$or": [
            {"doctorName": {"$regex": escaped, "$options": "i"}},
            {"doctorNameHindi": {"$regex": escaped, "$options": "i"}},
        ]
    })


def check_appointment_slots(date: str, doctor_name: str = "", department: str = "") -> str:
    """Check available 30-minute slots after subtracting already booked slots."""
    doctor = find_doctor(doctor_name) if doctor_name else None
    if not doctor and department:
        doctors = json.loads(list_doctors(department=department)).get("doctors", [])
        doctor = doctors[0] if doctors else None
    booked_query: dict[str, Any] = {"appointment_date": date, "status": {"$in": ["booked", "requested", "confirmed"]}}
    if doctor:
        booked_query["doctorName"] = doctor.get("doctorName")
    elif department:
        booked_query["department"] = {"$regex": f"^{re.escape(department)}$", "$options": "i"}
    booked = list(_bookings_collection().find(booked_query, {"_id": 0, "appointment_time": 1, "patient_name": 1, "status": 1}))
    booked_times = {item.get("appointment_time") for item in booked}
    all_slots = ["10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00"]
    available = [slot for slot in all_slots if slot not in booked_times]
    return _to_json({
        "date": date,
        "doctor": doctor,
        "department": department or (doctor or {}).get("department"),
        "availability_window": "Monday to Saturday, 10:00 to 16:00 IST",
        "available_slots": available,
        "booked_slots": booked,
    })


def create_booking(
    caller_id: str,
    patient_name: str,
    age: str,
    gender: str,
    appointment_date: str,
    appointment_time: str,
    doctor_name: str = "",
    department: str = "",
    phone: str = "",
    notes: str = "",
) -> str:
    """Create a real appointment booking/request in MongoDB."""
    doctor = find_doctor(doctor_name) if doctor_name else None
    resolved_department = department or (doctor or {}).get("department", "")
    existing = _bookings_collection().find_one({
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "doctorName": (doctor or {}).get("doctorName", doctor_name),
        "status": {"$in": ["booked", "requested", "confirmed"]},
    })
    if existing:
        return _to_json({"ok": False, "reason": "slot_already_booked", "existing_booking": existing})

    now = datetime.now(timezone.utc)
    booking = {
        "_id": str(uuid.uuid4()),
        "caller_id": caller_id or "anonymous",
        "phone": phone,
        "patient_name": patient_name,
        "age": age,
        "gender": gender,
        "doctorName": (doctor or {}).get("doctorName", doctor_name),
        "department": resolved_department,
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "status": "requested",
        "source": "voice_agent",
        "notes": notes,
        "createdAt": now,
        "updatedAt": now,
    }
    _bookings_collection().insert_one(booking)
    return _to_json({"ok": True, "booking": booking})


def update_booking(booking_id: str, status: str = "", appointment_date: str = "", appointment_time: str = "", notes: str = "") -> str:
    """Update booking status or reschedule details."""
    update: dict[str, Any] = {"updatedAt": datetime.now(timezone.utc)}
    if status:
        update["status"] = status
    if appointment_date:
        update["appointment_date"] = appointment_date
    if appointment_time:
        update["appointment_time"] = appointment_time
    if notes:
        update["notes"] = notes
    result = _bookings_collection().update_one({"_id": booking_id}, {"$set": update})
    return _to_json({"ok": result.modified_count > 0, "matched": result.matched_count, "booking_id": booking_id})


def retrieve_hospital_knowledge(query: str) -> str:
    """Retrieve relevant hospital policy/FAQ/document chunks using RAG."""
    try:
        chunks = retrieve_relevant_chunks(query, top_k=4)
    except Exception as exc:
        return _to_json({"ok": False, "error": f"RAG retrieval failed: {exc}", "chunks": []})
    return _to_json({"ok": True, "chunks": chunks})


def _initiate_twilio_outbound_call(phone_number: str, caller_id: str = "dashboard") -> str:
    request_doc = {
        "_id": str(uuid.uuid4()),
        "phone_number": phone_number,
        "caller_id": caller_id or "dashboard",
        "provider": "twilio",
        "status": "queued",
        "createdAt": datetime.now(timezone.utc),
    }
    get_db().get_collection("telephony_calls").insert_one(request_doc)

    stream_url = TWILIO_STREAM_URL or (PUBLIC_BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/ws/twilio" if PUBLIC_BASE_URL else None)
    voice_url = TWILIO_VOICE_URL or (f"{PUBLIC_BASE_URL}/api/telephony/twilio/voice" if PUBLIC_BASE_URL else None)
    required_config = {
        "TWILIO_ACCOUNT_SID": TWILIO_ACCOUNT_SID,
        "TWILIO_AUTH_TOKEN": TWILIO_AUTH_TOKEN,
        "TWILIO_PHONE_NUMBER": TWILIO_PHONE_NUMBER,
        "TWILIO_STREAM_URL_OR_PUBLIC_BASE_URL": stream_url,
    }
    missing_config = [name for name, value in required_config.items() if not value]
    if missing_config:
        get_db().get_collection("telephony_calls").update_one(
            {"_id": request_doc["_id"]},
            {"$set": {"status": "needs_configuration", "missing_config": missing_config}},
        )
        return _to_json({"ok": False, "reason": "twilio_not_configured", "missing_config": missing_config, "call": request_doc})

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls.json"
    # Trial accounts can reject optional webhook parameters. Use inline TwiML
    # so the outbound call can connect directly to the media stream without
    # requiring Twilio to fetch a Voice URL first.
    escaped_stream_url = html.escape(cast(str, stream_url), quote=True)
    twiml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<Response>"
        "<Say>Connecting you to the One Hospitals voice assistant.</Say>"
        f"<Connect><Stream url=\"{escaped_stream_url}\" /></Connect>"
        "</Response>"
    )
    payload = {
        "To": phone_number,
        "From": TWILIO_PHONE_NUMBER,
        "Twiml": twiml,
    }
    # Keep trial-account requests minimal. Status events can be enabled later
    # on a paid project.

    try:
        response = requests.post(
            url,
            data=payload,
            auth=(cast(str, TWILIO_ACCOUNT_SID), cast(str, TWILIO_AUTH_TOKEN)),
            timeout=20,
        )
        if response.status_code >= 400:
            raise requests.HTTPError(
                f"{response.status_code} {response.reason}: {response.text[:1000]}",
                response=response,
            )
        provider_response = response.text[:3000]
        get_db().get_collection("telephony_calls").update_one(
            {"_id": request_doc["_id"]},
            {"$set": {"status": "provider_submitted", "provider_response": provider_response, "request_url": url, "request_payload": payload, "updatedAt": datetime.now(timezone.utc)}},
        )
        return _to_json({"ok": True, "call_id": request_doc["_id"], "provider_response": provider_response})
    except Exception as exc:
        get_db().get_collection("telephony_calls").update_one(
            {"_id": request_doc["_id"]},
            {"$set": {"status": "provider_error", "error": str(exc), "request_url": url, "request_payload": payload, "updatedAt": datetime.now(timezone.utc)}},
        )
        return _to_json({"ok": False, "reason": "provider_error", "error": str(exc), "call": request_doc})


def initiate_outbound_call(phone_number: str, caller_id: str = "dashboard") -> str:
    """Start an outbound call with the configured provider."""
    if TELEPHONY_PROVIDER == "twilio":
        return _initiate_twilio_outbound_call(phone_number, caller_id)

    request_doc = {
        "_id": str(uuid.uuid4()),
        "phone_number": phone_number,
        "caller_id": caller_id or "dashboard",
        "provider": "exotel",
        "status": "queued",
        "createdAt": datetime.now(timezone.utc),
    }
    get_db().get_collection("telephony_calls").insert_one(request_doc)

    stream_url = EXOTEL_STREAM_URL or (EXOTEL_APP_URL.replace("https://", "wss://").replace("http://", "ws://").replace("/api/telephony/exotel/inbound", "/ws/exotel") if EXOTEL_APP_URL else None)
    flow_url = EXOTEL_FLOW_URL
    required_config = {
        "EXOTEL_ACCOUNT_SID": EXOTEL_ACCOUNT_SID,
        "EXOTEL_API_KEY": EXOTEL_API_KEY,
        "EXOTEL_API_TOKEN": EXOTEL_API_TOKEN,
        "EXOTEL_CALLER_ID": EXOTEL_CALLER_ID,
        "EXOTEL_FLOW_URL_OR_STREAM_URL": flow_url or stream_url,
    }
    missing_config = [name for name, value in required_config.items() if not value]
    if missing_config:
        request_doc["status"] = "needs_configuration"
        request_doc["missing_config"] = missing_config
        get_db().get_collection("telephony_calls").update_one(
            {"_id": request_doc["_id"]},
            {"$set": {"status": "needs_configuration", "missing_config": missing_config}},
        )
        return _to_json({"ok": False, "reason": "exotel_not_configured", "missing_config": missing_config, "call": request_doc})

    # Prefer calling through the saved Exotel flow when configured. This is
    # usually supported on trial/student accounts and lets the flow's Voicebot
    # applet connect to /ws/exotel. Direct AgentStream streamurl can be rejected
    # if the account is not enabled for that API.
    url = f"{EXOTEL_API_BASE_URL}/v1/Accounts/{EXOTEL_ACCOUNT_SID}/Calls/connect.json"
    if flow_url:
        payload = {
            "From": phone_number,
            "CallerId": EXOTEL_CALLER_ID,
            "Url": flow_url,
            "CallType": "trans",
            "CustomField": caller_id or "dashboard",
        }
        if EXOTEL_STATUS_CALLBACK_URL:
            payload["StatusCallback"] = EXOTEL_STATUS_CALLBACK_URL
    else:
        payload = {
            "From": phone_number,
            "CallerId": EXOTEL_CALLER_ID,
            "StreamUrl": stream_url,
            "StreamType": "bidirectional",
            "Record": "true",
            "CustomField": caller_id or "dashboard",
        }
        if EXOTEL_STATUS_CALLBACK_URL:
            payload["StatusCallback"] = EXOTEL_STATUS_CALLBACK_URL
    try:
        api_key = cast(str, EXOTEL_API_KEY)
        api_token = cast(str, EXOTEL_API_TOKEN)
        response = requests.post(url, data=payload, auth=(api_key, api_token), timeout=20)
        if response.status_code >= 400:
            raise requests.HTTPError(
                f"{response.status_code} {response.reason}: {response.text[:1000]}",
                response=response,
            )
        provider_response = response.text[:2000]
        get_db().get_collection("telephony_calls").update_one(
            {"_id": request_doc["_id"]},
            {"$set": {"status": "provider_submitted", "provider_response": provider_response, "updatedAt": datetime.now(timezone.utc)}},
        )
        return _to_json({"ok": True, "call_id": request_doc["_id"], "provider_response": provider_response})
    except Exception as exc:
        get_db().get_collection("telephony_calls").update_one(
            {"_id": request_doc["_id"]},
            {"$set": {"status": "provider_error", "error": str(exc), "request_url": url, "request_payload": payload, "updatedAt": datetime.now(timezone.utc)}},
        )
        return _to_json({"ok": False, "reason": "provider_error", "error": str(exc), "call": request_doc})


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return tool definitions in an OpenAI-style function-calling schema."""
    return [
        {
            "type": "function",
            "function": {
                "name": "list_doctors",
                "description": "Find real doctors from MongoDB by department or health issue. Use before suggesting doctors.",
                "parameters": {"type": "object", "properties": {"department": {"type": "string"}, "health_issue": {"type": "string"}}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_appointment_slots",
                "description": "Check available slots for a doctor or department on a YYYY-MM-DD date, including booked slots.",
                "parameters": {
                    "type": "object",
                    "properties": {"date": {"type": "string"}, "doctor_name": {"type": "string"}, "department": {"type": "string"}},
                    "required": ["date"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_booking",
                "description": "Create the appointment booking/request after all required fields are collected and the slot is valid.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "caller_id": {"type": "string"},
                        "patient_name": {"type": "string"},
                        "age": {"type": "string"},
                        "gender": {"type": "string"},
                        "appointment_date": {"type": "string"},
                        "appointment_time": {"type": "string", "description": "24-hour HH:MM IST"},
                        "doctor_name": {"type": "string"},
                        "department": {"type": "string"},
                        "phone": {"type": "string"},
                        "notes": {"type": "string"},
                    },
                    "required": ["caller_id", "patient_name", "age", "gender", "appointment_date", "appointment_time"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_booking",
                "description": "Update, cancel, confirm, or reschedule an existing booking by booking id.",
                "parameters": {"type": "object", "properties": {"booking_id": {"type": "string"}, "status": {"type": "string"}, "appointment_date": {"type": "string"}, "appointment_time": {"type": "string"}, "notes": {"type": "string"}}, "required": ["booking_id"]},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "retrieve_hospital_knowledge",
                "description": "Use RAG to answer hospital policy, uploaded PDF/document, doctor, FAQ, or service questions from MongoDB knowledge_base.",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "initiate_outbound_call",
                "description": "Initiate an outbound Exotel call from the dashboard/agent when a phone number is provided.",
                "parameters": {"type": "object", "properties": {"phone_number": {"type": "string"}, "caller_id": {"type": "string"}}, "required": ["phone_number"]},
            },
        },
    ]
