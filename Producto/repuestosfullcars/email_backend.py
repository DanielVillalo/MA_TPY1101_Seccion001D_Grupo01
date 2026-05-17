import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = settings.BREVO_API_KEY
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
        sent = 0
        for message in email_messages:
            try:
                to = [{"email": addr} for addr in message.to]
                send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                    to=to,
                    sender={"email": settings.DEFAULT_FROM_EMAIL},
                    subject=message.subject,
                    text_content=message.body,
                )
                api_instance.send_transac_email(send_smtp_email)
                sent += 1
            except ApiException as e:
                if not self.fail_silently:
                    raise
        return sent