"""
Management command: test_telegram_notification

Tests the Telegram Bot notification service.

Usage:
    python manage.py test_telegram_notification [--token=...] [--chat-id=...]
"""

import os
from django.core.management.base import BaseCommand
from django_forms_workflows.services.telegram_service import (
    is_telegram_enabled,
    send_telegram_message,
)


class Command(BaseCommand):
    help = "Tests Telegram Bot connection by sending a sample alert message."

    def add_arguments(self, parser):
        parser.add_argument("--token", type=str, help="Telegram Bot Token")
        parser.add_argument("--chat-id", type=str, help="Telegram Target Chat/Group ID")

    def handle(self, *args, **options):
        token = options.get("token")
        chat_id = options.get("chat_id")

        if token:
            os.environ["TELEGRAM_BOT_TOKEN"] = token
        if chat_id:
            os.environ["TELEGRAM_CHAT_ID"] = chat_id

        if not is_telegram_enabled():
            self.stdout.write(
                self.style.ERROR(
                    "[ERROR] Telegram belum dikonfigurasi!\n"
                    "Harap tentukan TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di .env atau via argumen:\n"
                    "  python manage.py test_telegram_notification --token='...' --chat-id='...'"
                )
            )
            return

        self.stdout.write("Mengirim pesan uji coba ke Telegram...")
        sample_message = (
            "🚀 *[VERIFIKASI SISTEM] KONEKSI TELEGRAM BOT BERHASIL!*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Halo! Layanan notifikasi Telegram untuk *Royal Workflow* telah berhasil terhubung.\n\n"
            "Setiap pengajuan baru, permohonan persetujuan, dan reminder otomatis akan dikirimkan ke chat/grup ini.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "_Royal Workflow Enterprise Notification Engine_"
        )

        success = send_telegram_message(sample_message)
        if success:
            self.stdout.write(
                self.style.SUCCESS("[SUCCESS] Pesan uji coba berhasil terkirim ke Telegram!")
            )
        else:
            self.stdout.write(
                self.style.ERROR("[FAILED] Gagal mengirim pesan ke Telegram. Periksa log atau kredensial.")
            )
