from io import BytesIO
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.http import HttpResponse
from django.conf import settings
from django.core.mail import EmailMessage

def generate_invoice_pdf(order):
    template = get_template('orders/invoice.html')
    context = {
        'order': order,
        'company_name': 'Interio Furnitures',
        'company_address': 'Your Company Address',
        'company_phone': 'Your Company Phone',
    }
    html = template.render(context)
    
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        return result.getvalue()
    return None

def send_invoice_email(order):
    subject = f'Your Order Invoice #{order.id} - Interio Furnitures'
    message = 'Please find attached your order invoice.'
    email = EmailMessage(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.user.email]
    )
    
    # Generate PDF
    pdf = generate_invoice_pdf(order)
    if pdf:
        email.attach(f'invoice_{order.id}.pdf', pdf, 'application/pdf')
        email.send()
        return True
    return False