"""Service pour gestion configuration Trello (table Config)."""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from datetime import datetime
from app import db
from app.models.trello_models import Config


class ConfigService:
    @staticmethod
    def create(raw_data: Dict[str, Any]) -> Config:
        cfg = Config(config_data=raw_data)
        db.session.add(cfg)
        db.session.commit()
        return cfg

    @staticmethod
    def update(config_id: int, updates: Dict[str, Any]) -> Optional[Config]:
        cfg = Config.query.get(config_id)
        if not cfg:
            return None
        data = cfg.config_data.copy()
        data.update({k: v for k, v in updates.items() if v is not None})
        cfg.config_data = data
        cfg.updatedAt = datetime.utcnow()
        db.session.commit()
        return cfg

    @staticmethod
    def list_all() -> List[Config]:
        return Config.query.all()

    @staticmethod
    def set_target_list(config_id: int, target_list_id: str, target_list_name: str):
        cfg = Config.query.get(config_id)
        if not cfg:
            return None
        data = cfg.config_data.copy()
        data['targetListId'] = target_list_id
        data['targetListName'] = target_list_name
        cfg.config_data = data
        db.session.commit()
        return cfg

    @staticmethod
    def latest() -> Optional[Config]:  # pragma: no cover
        return Config.get_latest_config()
