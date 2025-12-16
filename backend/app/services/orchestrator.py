from pathlib import Path
from sqlalchemy.orm import Session
from .. import models
from ..config import get_settings
from ..providers.mocks import MockLLM, MockVideoProvider, MockTikTokPublisher, MockASR, LocalStorage
from ..providers.base import LLMProvider, VideoProvider, TikTokPublisher, ASRProvider, StorageProvider


settings = get_settings()


def _select_provider(mock_cls, real_instance):
    return mock_cls if settings.use_mock_providers or real_instance is None else real_instance


class Orchestrator:
    def __init__(
        self,
        llm: LLMProvider | None = None,
        video: VideoProvider | None = None,
        publisher: TikTokPublisher | None = None,
        asr: ASRProvider | None = None,
        storage: StorageProvider | None = None,
    ):
        self.llm: LLMProvider = _select_provider(MockLLM(), llm)
        self.video: VideoProvider = _select_provider(MockVideoProvider(settings.ffmpeg_path), video)
        self.publisher: TikTokPublisher = _select_provider(MockTikTokPublisher(), publisher)
        self.asr: ASRProvider = _select_provider(MockASR(), asr)
        self.storage: StorageProvider = storage or LocalStorage(settings.storage_path)

    def generate_assets(self, db: Session, project: models.Project, plan: models.Plan | None = None) -> models.VideoAsset:
        prompt = f"Create a TikTok script for project {project.name}"
        completion = self.llm.complete(prompt)
        script = completion.get("script", "")
        asset_dir = Path(settings.storage_path) / project.id
        video_path = asset_dir / f"{plan.id if plan else 'adhoc'}_final.mp4"
        thumb_path = asset_dir / f"{plan.id if plan else 'adhoc'}_thumbnail.jpg"
        self.video.render(script, str(video_path), str(thumb_path))
        transcript = self.asr.transcribe(str(video_path))
        asset = models.VideoAsset(
            project_id=project.id,
            plan_id=plan.id if plan else None,
            status="generated",
            video_path=str(video_path),
            thumbnail_path=str(thumb_path),
            transcript=transcript,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset

    def publish_now(self, asset: models.VideoAsset, caption: str = "Auto-post") -> dict:
        return self.publisher.publish(asset.video_path, caption)
