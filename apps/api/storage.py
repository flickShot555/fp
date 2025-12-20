import json
import os
from typing import Dict, Any, List, Optional


class ResponseStore:
    def __init__(self, base_dir: str = "./data"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.path = os.path.join(self.base_dir, "response.json")
        if not os.path.exists(self.path):
            self._write({"documents": {}, "chats": [], "chunks": []})

    def _read(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"documents": {}, "chats": [], "chunks": []}

    def _write(self, data: Dict[str, Any]):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def save_document(self, record: Dict[str, Any]):
        data = self._read()
        docs = data.get("documents", {})
        docs[record["id"]] = record
        data["documents"] = docs
        self._write(data)

    # Loads and carriers for matching workflows
    def save_load(self, load: Dict[str, Any]):
        data = self._read()
        loads = data.get("loads", {})
        loads[load["id"]] = load
        data["loads"] = loads
        self._write(data)

    def get_load(self, load_id: str) -> Optional[Dict[str, Any]]:
        data = self._read()
        return data.get("loads", {}).get(load_id)

    def list_loads(self) -> List[Dict[str, Any]]:
        data = self._read()
        return list(data.get("loads", {}).values())

    def save_carrier(self, carrier: Dict[str, Any]):
        data = self._read()
        carriers = data.get("carriers", {})
        carriers[carrier["id"]] = carrier
        data["carriers"] = carriers
        self._write(data)

    def get_carrier(self, carrier_id: str) -> Optional[Dict[str, Any]]:
        data = self._read()
        return data.get("carriers", {}).get(carrier_id)

    def list_carriers(self) -> List[Dict[str, Any]]:
        data = self._read()
        return list(data.get("carriers", {}).values())

    def save_assignment(self, assignment: Dict[str, Any]):
        data = self._read()
        assignments = data.get("assignments", [])
        assignments.append(assignment)
        data["assignments"] = assignments
        self._write(data)

    def list_assignments(self) -> List[Dict[str, Any]]:
        data = self._read()
        return data.get("assignments", [])

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        data = self._read()
        return data.get("documents", {}).get(doc_id)

    def list_documents(self) -> List[Dict[str, Any]]:
        data = self._read()
        return list(data.get("documents", {}).values())

    def append_chat(self, chat: Dict[str, Any]):
        data = self._read()
        chats = data.get("chats", [])
        chats.append(chat)
        data["chats"] = chats
        self._write(data)

    def save_fmcsa_profile(self, profile: Dict[str, Any]):
        data = self._read()
        carrier_data = data.get("fmcsa_profiles", {})
        key = profile.get("usdot")
        if not key:
            return
        carrier_data[key] = profile
        data["fmcsa_profiles"] = carrier_data
        self._write(data)

    def get_fmcsa_profile(self, usdot: str) -> Optional[Dict[str, Any]]:
        data = self._read()
        return data.get("fmcsa_profiles", {}).get(usdot)

    def save_fmcsa_verification(self, verification: Dict[str, Any]):
        data = self._read()
        verifications = data.get("fmcsa_verifications", {})
        key = verification.get("usdot") or verification.get("mc_number")
        if not key:
            return
        verifications[key] = verification
        data["fmcsa_verifications"] = verifications
        self._write(data)

    def get_fmcsa_verification(self, key: str) -> Optional[Dict[str, Any]]:
        data = self._read()
        return data.get("fmcsa_verifications", {}).get(key)

    # Alerts
    def save_alert(self, alert: Dict[str, Any]):
        data = self._read()
        alerts = data.get("alerts", [])
        # de-dup simple: skip if identical type/message/entity exists
        for a in alerts:
            if (
                a.get("type") == alert.get("type")
                and a.get("message") == alert.get("message")
                and a.get("entity_id") == alert.get("entity_id")
            ):
                return
        alerts.append(alert)
        data["alerts"] = alerts
        self._write(data)

    def list_alerts(self, priority: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self._read()
        alerts = data.get("alerts", [])
        if priority:
            alerts = [a for a in alerts if a.get("priority") == priority]
        return alerts

    def alert_summary(self) -> Dict[str, int]:
        data = self._read()
        alerts = data.get("alerts", [])
        summary: Dict[str, int] = {}
        for a in alerts:
            pr = a.get("priority") or "routine"
            summary[pr] = summary.get(pr, 0) + 1
        return summary

    def save_alert_digest(self, digest: Dict[str, Any]):
        data = self._read()
        data["alert_digest"] = digest
        self._write(data)

    def get_alert_digest(self) -> Optional[Dict[str, Any]]:
        data = self._read()
        return data.get("alert_digest")

    # Chunk/Embedding management
    def upsert_document_chunks(self, document_id: str, chunks: List[Dict[str, Any]]):
        """Replace all chunks for a document id with provided list.
        Each chunk requires: {id, document_id, chunk_index, content, embedding(list[float]), metadata}
        """
        data = self._read()
        existing = data.get("chunks", [])
        # remove old
        filtered = [c for c in existing if c.get("document_id") != document_id]
        # add new
        filtered.extend(chunks)
        data["chunks"] = filtered
        self._write(data)

    def get_all_chunks(self) -> List[Dict[str, Any]]:
        data = self._read()
        return list(data.get("chunks", []))
