from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import settings_dep
from app.config import Settings
from app.db.session import get_db
from app.models import Company
from app.schemas.api import CompanyCreate, CompanyOut, IngestionRunOut
from app.services.ingestion import get_or_create_company, run_ats_ingestion

router = APIRouter(prefix="/companies", tags=["companies"])


def _out(c: Company) -> CompanyOut:
    return CompanyOut(id=c.id, name=c.name, ats_type=c.ats_type, ats_slug=c.ats_slug, website=c.website)


@router.post("", response_model=CompanyOut)
def create_company(body: CompanyCreate, db: Session = Depends(get_db)):
    if body.ats_type and body.ats_type not in ("greenhouse", "lever"):
        raise HTTPException(422, "ats_type must be greenhouse or lever")
    return _out(get_or_create_company(db, body.name, body.ats_type, body.ats_slug, body.website))


@router.get("", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db)):
    return [_out(c) for c in db.scalars(select(Company).order_by(Company.name)).all()]


@router.post("/{company_id}/ingest", response_model=IngestionRunOut)
def ingest_company_board(
    company_id: int, refresh: bool = False, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)
):
    """Fetch the company's ATS board. refresh=true bypasses the API cache to re-verify postings now."""
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "Company not found")
    if not company.ats_type or not company.ats_slug:
        raise HTTPException(422, "Company has no ATS type/slug configured")
    run = run_ats_ingestion(db, settings, company, refresh=refresh)
    return IngestionRunOut.model_validate(run, from_attributes=True)
