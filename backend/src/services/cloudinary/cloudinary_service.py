import asyncio

import cloudinary
import cloudinary.uploader
import cloudinary.api

from src.config import get_settings

settings = get_settings()

cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
    secure=True,
)


class CloudinaryService:
    async def upload_image(self, file_path: str, folder: str = "patient_photos") -> dict:
        # cloudinary's SDK is synchronous (blocking network I/O) — run it off
        # the event loop rather than stalling every other in-flight request.
        result = await asyncio.to_thread(cloudinary.uploader.upload, file_path, folder=folder)
        return {
            "public_id": result["public_id"],
            "url": result["secure_url"],
            "width": result.get("width"),
            "height": result.get("height"),
        }

    async def upload_from_bytes(
        self, file_bytes: bytes, filename: str, folder: str = "patient_photos", resource_type: str = "image"
    ) -> dict:
        # resource_type="raw" is required for non-image files (PDFs, etc.) —
        # Cloudinary's default "image" upload validates/transforms as an
        # image and rejects anything else.
        result = await asyncio.to_thread(
            cloudinary.uploader.upload, file_bytes, folder=folder, public_id=filename, resource_type=resource_type
        )
        return {
            "public_id": result["public_id"],
            "url": result["secure_url"],
        }

    async def delete_image(self, public_id: str):
        await asyncio.to_thread(cloudinary.uploader.destroy, public_id)
