from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    client_name: str = ""


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    client_name: str
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime


class ConnectionCreate(BaseModel):
    connector_type: str


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    connector_type: str
    status: str
