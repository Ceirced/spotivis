from celery import Celery, Task, shared_task  # type: ignore
from flask import Flask
from app.extensions import mail  # type: ignore
from flask_mailman import EmailMultiAlternatives  # type: ignore
from flask_security import MailUtil


def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app


@shared_task
def send_flask_mail(**kwargs):
    with mail.get_connection() as connection:
        html = kwargs.pop("html", None)
        msg = EmailMultiAlternatives(
            **kwargs,
            connection=connection,
        )
        if html:
            msg.attach_alternative(html, "text/html")
        msg.send()


class CeleryMailUtil(MailUtil):
    def send_mail(self, template, subject, recipient, sender, body, html, **kwargs):
        print(f"Sending email to {recipient} with subject: {subject}")
        send_flask_mail.delay(
            subject=subject, body=body, html=html, to=[recipient], from_email=sender
        )
