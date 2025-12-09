from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/requests", tags=["Requests"])

@router.post("/", response_model=schemas.RequestOut)
def create_request(req: schemas.RequestCreate, db: Session = Depends(get_db)):
    new = models.Request(
        customer_name=req.customer_name,
        service_type=req.service_type,
        location=req.location,
        description=req.description,
    )
    db.add(new)
    db.commit()
    db.refresh(new)
    return new

@router.get("/", response_model=List[schemas.RequestOut])
def get_requests(db: Session = Depends(get_db)):
    return db.query(models.Request).all()

@router.get("/{request_id}", response_model=schemas.RequestOut)
def get_request(request_id: int, db: Session = Depends(get_db)):
    req = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return req

@router.patch("/{request_id}/status", response_model=schemas.RequestOut)
def update_status(request_id: int, status: str, db: Session = Depends(get_db)):
    req = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    req.status = status
    db.add(req)
    db.commit()
    db.refresh(req)
    return req

@router.delete("/{request_id}")
def delete_request(request_id: int, db: Session = Depends(get_db)):
    req = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    db.delete(req)
    db.commit()
    return {"detail": "Request deleted successfully"}
