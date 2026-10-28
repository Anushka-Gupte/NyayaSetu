"""Small Google Meet REST client used to provision hearing spaces.

The application uses an administrator-provisioned OAuth refresh token. Google
Meet's API requires user OAuth; a service-account-only integration is not
supported by this flow.
"""

from typing import Tuple

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


class GoogleMeetService:
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SPACES_URL = "https://meet.googleapis.com/v2/spaces"
    REQUIRED_SETTINGS = (
        "GOOGLE_MEET_CLIENT_ID",
        "GOOGLE_MEET_CLIENT_SECRET",
        "GOOGLE_MEET_REFRESH_TOKEN",
    )

    @classmethod
    def is_configured(cls) -> bool:
        return all(getattr(settings, name) for name in cls.REQUIRED_SETTINGS)

    @classmethod
    def create_space(cls) -> Tuple[str, str]:
        """Create a restricted Meet space; return (meeting URI, resource name)."""
        if not cls.is_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Google Meet is selected but not configured. Set "
                    "GOOGLE_MEET_CLIENT_ID, GOOGLE_MEET_CLIENT_SECRET, and "
                    "GOOGLE_MEET_REFRESH_TOKEN."
                ),
            )

        try:
            with httpx.Client(timeout=20.0) as client:
                token_response = client.post(
                    cls.TOKEN_URL,
                    data={
                        "client_id": settings.GOOGLE_MEET_CLIENT_ID,
                        "client_secret": settings.GOOGLE_MEET_CLIENT_SECRET,
                        "refresh_token": settings.GOOGLE_MEET_REFRESH_TOKEN,
                        "grant_type": "refresh_token",
                    },
                )
                token_response.raise_for_status()
                access_token = token_response.json().get("access_token")
                if not access_token:
                    raise ValueError("Google OAuth response did not include an access token")

                space_response = client.post(
                    cls.SPACES_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"config": {"accessType": "RESTRICTED"}},
                )
                space_response.raise_for_status()
                space = space_response.json()

            meeting_uri = space.get("meetingUri")
            space_name = space.get("name")
            if not meeting_uri or not space_name:
                raise ValueError("Google Meet did not return meetingUri and name")
            return meeting_uri, space_name
        except httpx.HTTPStatusError as exc:
            # Avoid returning provider response bodies, which can contain details
            # that should remain in server logs rather than the public API.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Google Meet API request failed (HTTP {exc.response.status_code}).",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not provision a Google Meet space. Check the OAuth credentials and Google Meet API configuration.",
            ) from exc
