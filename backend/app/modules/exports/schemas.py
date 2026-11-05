from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExportCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mode: Literal['metadata','originals']='metadata'
    event_set_ids: list[int]=Field(default_factory=list,max_length=20)
    report_ids: list[int]=Field(default_factory=list,max_length=100)
    evidence_ids: list[int]=Field(default_factory=list,max_length=100)

    @model_validator(mode='after')
    def selection(self):
        for name in ('event_set_ids','report_ids','evidence_ids'):
            values=getattr(self,name)
            if any(value<=0 for value in values): raise ValueError('Selection identifiers must be positive.')
            setattr(self,name,sorted(set(values)))
        if (self.mode=='originals')!=bool(self.evidence_ids):
            raise ValueError('Originals mode requires an explicit nonempty evidence selection; metadata mode cannot include original bytes.')
        return self


class ExportRead(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int
    investigation_id:int
    requested_by_id:int|None
    mode:str
    status:str
    selection:dict
    package_sha256:str|None
    byte_size:int|None
    manifest_summary:dict
    error:str|None
    created_at:datetime
    completed_at:datetime|None
