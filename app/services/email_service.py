import os
from brevo import Brevo
from brevo.transactional_emails import (
    SendTransacEmailRequestSender,
    SendTransacEmailRequestToItem,
)

class EmailService:
    @staticmethod
    def send_transactional_email(to_email: str, name: str, subject: str, html_content: str):
        # Inicializa el cliente usando tu variable de entorno
        client = Brevo(api_key=os.environ.get("BREVO_API_KEY"))
        
        try:
            result = client.transactional_emails.send_transac_email(
                subject=subject,
                html_content=html_content,
                sender=SendTransacEmailRequestSender(
                    name="Tu Empresa",
                    email="correo-verificado@tu-dominio.com"  # Debe estar verificado en Brevo
                ),
                to=[
                    SendTransacEmailRequestToItem(
                        email=to_email,
                        name=name
                    )
                ]
            )
            return {"success": True, "message_id": getattr(result, "message_id", "Enviado")}
        except Exception as e:
            return {"success": False, "error": str(e)}