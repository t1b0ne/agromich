from fastapi import APIRouter, HTTPException
from app.schemas.email_schema import EmailSchema
from app.services.email_service import EmailService

router = APIRouter(prefix="/emails", tags=["Emails"])

@router.post("/send")
def send_email_endpoint(payload: EmailSchema):
    result = EmailService.send_transactional_email(
        to_email=payload.email,
        name=payload.name,
        subject=payload.subject,
        html_content=payload.html_content
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Error al enviar correo: {result['error']}")
    
    return {
        "message": "Correo enviado con éxito",
        "details": result
    }