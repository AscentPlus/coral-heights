from .models import ContactInformation


def contact_info(request):
    """
    Context processor to provide hotel contact details, phone numbers,
    emails, and social media URLs across all site templates.
    """
    info = ContactInformation.objects.first()
    if not info:
        info = ContactInformation.objects.create()
    return {
        'contact_info': info
    }
