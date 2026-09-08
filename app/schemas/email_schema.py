from pydantic import BaseModel, EmailStr

class EmailSchema(BaseModel):
    email: EmailStr
    name: str
    subject: str
    html_content: str