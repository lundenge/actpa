"""Email send/receive helpers.

Provides a small, dependency-free helper using the Python standard
library to send emails (SMTP) and receive emails (IMAP/POP3).

Configuration is read from environment variables or passed in via
an EmailConfig object.

This file aims to be lightweight and safe to import in a FastAPI app.
"""
from __future__ import annotations

import os
import ssl
import smtplib
import imaplib
import poplib
import email
from email.message import EmailMessage
from email.header import decode_header
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
import asyncio


@dataclass
class EmailConfig:
	smtp_host: str
	smtp_port: int = 587
	smtp_use_tls: bool = True  # starttls
	smtp_user: Optional[str] = None
	smtp_password: Optional[str] = None
	default_from: Optional[str] = None

	imap_host: Optional[str] = None
	imap_port: int = 993
	imap_ssl: bool = True

	pop3_host: Optional[str] = None
	pop3_port: int = 995
	pop3_ssl: bool = True

	@classmethod
	def from_env(cls) -> "EmailConfig":
		return cls(
			smtp_host=os.getenv("SMTP_HOST", ""),
			smtp_port=int(os.getenv("SMTP_PORT", "587")),
			smtp_use_tls=os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes"),
			smtp_user=os.getenv("SMTP_USER"),
			smtp_password=os.getenv("SMTP_PASSWORD"),
			default_from=os.getenv("SMTP_FROM"),
			imap_host=os.getenv("IMAP_HOST"),
			imap_port=int(os.getenv("IMAP_PORT", "993")),
			imap_ssl=os.getenv("IMAP_SSL", "true").lower() in ("1", "true", "yes"),
			pop3_host=os.getenv("POP3_HOST"),
			pop3_port=int(os.getenv("POP3_PORT", "995")),
			pop3_ssl=os.getenv("POP3_SSL", "true").lower() in ("1", "true", "yes"),
		)


def _decode_header_value(value: Optional[bytes]) -> str:
	if not value:
		return ""
	if isinstance(value, bytes):
		value = value.decode(errors="ignore")
	parts = decode_header(value)
	pieces = []
	for part, encoding in parts:
		if isinstance(part, bytes):
			try:
				pieces.append(part.decode(encoding or "utf-8", errors="ignore"))
			except Exception:
				pieces.append(part.decode("utf-8", errors="ignore"))
		else:
			pieces.append(part)
	return "".join(pieces)


def _get_message_text(msg: email.message.Message) -> Tuple[str, Optional[str]]:
	"""Return (plain_text, html) from a message object."""
	plain = []
	html = None
	if msg.is_multipart():
		for part in msg.walk():
			ctype = part.get_content_type()
			disp = part.get("Content-Disposition", None)
			if disp is not None and disp.strip().startswith("attachment"):
				# skip attachments here
				continue
			try:
				payload = part.get_payload(decode=True)
			except Exception:
				payload = None
			if payload is None:
				continue
			try:
				text = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
			except Exception:
				text = payload.decode("utf-8", errors="ignore")
			if ctype == "text/plain":
				plain.append(text)
			elif ctype == "text/html":
				html = text
	else:
		payload = msg.get_payload(decode=True)
		if payload:
			try:
				plain.append(payload.decode(msg.get_content_charset() or "utf-8", errors="ignore"))
			except Exception:
				plain.append(payload.decode("utf-8", errors="ignore"))

	return ("\n".join(plain).strip(), html)


class EmailService:
	"""Simple email service providing send and receive helpers.

	Uses only the standard library (smtplib, imaplib, poplib). For
	production use you may want to swap in a higher-level client or
	an async SMTP client.
	"""

	def __init__(self, config: EmailConfig):
		self.config = config

	def send_email(
		self,
		to_addresses: List[str],
		subject: str,
		body: str,
		html: Optional[str] = None,
		cc: Optional[List[str]] = None,
		bcc: Optional[List[str]] = None,
		from_address: Optional[str] = None,
	) -> None:
		"""Send an email via SMTP (blocking).

		Raises smtplib.SMTPException on failure.
		"""
		if from_address is None:
			from_address = self.config.default_from or self.config.smtp_user
		msg = EmailMessage()
		msg["Subject"] = subject
		msg["From"] = from_address
		msg["To"] = ", ".join(to_addresses)
		if cc:
			msg["Cc"] = ", ".join(cc)

		all_recipients = list(to_addresses) + (cc or []) + (bcc or [])

		if html:
			msg.set_content(body)
			msg.add_alternative(html, subtype="html")
		else:
			msg.set_content(body)

		# choose connection method
		if self.config.smtp_use_tls:
			# Start with plain SMTP and upgrade to TLS via STARTTLS
			server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=30)
			try:
				server.ehlo()
				server.starttls(context=ssl.create_default_context())
				server.ehlo()
				if self.config.smtp_user and self.config.smtp_password:
					server.login(self.config.smtp_user, self.config.smtp_password)
				server.send_message(msg, from_addr=from_address, to_addrs=all_recipients)
			finally:
				try:
					server.quit()
				except Exception:
					server.close()
		else:
			# No TLS: try SSL first
			server = smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, context=ssl.create_default_context())
			try:
				if self.config.smtp_user and self.config.smtp_password:
					server.login(self.config.smtp_user, self.config.smtp_password)
				server.send_message(msg, from_addr=from_address, to_addrs=all_recipients)
			finally:
				try:
					server.quit()
				except Exception:
					server.close()

	async def send_email_async(self, *args, **kwargs) -> None:
		"""Async wrapper for send_email using asyncio.to_thread."""
		return await asyncio.to_thread(self.send_email, *args, **kwargs)

	def fetch_unseen_imap(self, folder: str = "INBOX", limit: int = 20, mark_seen: bool = False) -> List[Dict[str, Any]]:
		"""Fetch unseen messages from IMAP mailbox and return parsed list.

		Each item is a dict with keys: subject, from, to, date, plain, html, raw
		"""
		if not self.config.imap_host:
			raise ValueError("IMAP host not configured")

		if self.config.imap_ssl:
			imap = imaplib.IMAP4_SSL(self.config.imap_host, self.config.imap_port)
		else:
			imap = imaplib.IMAP4(self.config.imap_host, self.config.imap_port)

		try:
			if self.config.imap_host and self.config.smtp_user and self.config.smtp_password:
				# reuse smtp_user/password if IMAP credentials are the same
				imap.login(self.config.smtp_user, self.config.smtp_password)
			elif self.config.smtp_user and self.config.smtp_password:
				# try anyway
				try:
					imap.login(self.config.smtp_user, self.config.smtp_password)
				except Exception:
					pass

			imap.select(folder)
			status, data = imap.search(None, "UNSEEN")
			if status != "OK":
				return []
			ids = data[0].split()[::-1]  # newest first
			results: List[Dict[str, Any]] = []
			for idx in ids[:limit]:
				typ, msg_data = imap.fetch(idx, "(RFC822)")
				if typ != "OK":
					continue
				raw = msg_data[0][1]
				msg = email.message_from_bytes(raw)
				subject = _decode_header_value(msg.get("Subject"))
				from_ = _decode_header_value(msg.get("From"))
				to = _decode_header_value(msg.get("To"))
				date = msg.get("Date")
				plain, html = _get_message_text(msg)
				results.append({
					"subject": subject,
					"from": from_,
					"to": to,
					"date": date,
					"plain": plain,
					"html": html,
					"raw": raw,
				})
				if not mark_seen:
					# remove the \Seen flag if we set it implicitly
					try:
						imap.store(idx, "-FLAGS", "\\Seen")
					except Exception:
						pass

			return results
		finally:
			try:
				imap.close()
			except Exception:
				pass
			try:
				imap.logout()
			except Exception:
				pass

	def fetch_pop3(self, limit: int = 10) -> List[Dict[str, Any]]:
		"""Fetch latest messages from POP3 server.

		Returns a list like fetch_unseen_imap.
		"""
		if not self.config.pop3_host:
			raise ValueError("POP3 host not configured")

		if self.config.pop3_ssl:
			pop = poplib.POP3_SSL(self.config.pop3_host, self.config.pop3_port, timeout=30)
		else:
			pop = poplib.POP3(self.config.pop3_host, self.config.pop3_port, timeout=30)

		try:
			if self.config.smtp_user and self.config.smtp_password:
				try:
					pop.user(self.config.smtp_user)
					pop.pass_(self.config.smtp_password)
				except Exception:
					pass

			resp, items, octets = pop.list()
			# items is list of b'1 1234' entries
			ids = [int(x.split()[0]) for x in items]
			ids.sort(reverse=True)
			results: List[Dict[str, Any]] = []
			for i in ids[:limit]:
				try:
					resp, lines, octets = pop.retr(i)
					raw = b"\r\n".join(lines)
					msg = email.message_from_bytes(raw)
					subject = _decode_header_value(msg.get("Subject"))
					from_ = _decode_header_value(msg.get("From"))
					to = _decode_header_value(msg.get("To"))
					date = msg.get("Date")
					plain, html = _get_message_text(msg)
					results.append({
						"subject": subject,
						"from": from_,
						"to": to,
						"date": date,
						"plain": plain,
						"html": html,
						"raw": raw,
					})
				except Exception:
					continue
			return results
		finally:
			try:
				pop.quit()
			except Exception:
				try:
					pop.close()
				except Exception:
					pass


if __name__ == "__main__":
	# Simple demo when run directly. Configure via environment variables.
	cfg = EmailConfig.from_env()
	svc = EmailService(cfg)

	# Example send (only runs if SMTP_HOST & SMTP_USER are set)
	if cfg.smtp_host and cfg.smtp_user and cfg.smtp_password and cfg.default_from:
		try:
			svc.send_email(
				to_addresses=[cfg.smtp_user],
				subject="Test from EmailService",
				body="This is a test message sent by EmailService",
				from_address=cfg.default_from,
			)
			print("Email sent (if SMTP settings are correct)")
		except Exception as e:
			print("Send failed:", e)

	# Example IMAP fetch
	if cfg.imap_host and cfg.smtp_user and cfg.smtp_password:
		try:
			msgs = svc.fetch_unseen_imap(limit=5)
			print(f"Fetched {len(msgs)} IMAP messages")
		except Exception as e:
			print("IMAP fetch failed:", e)

