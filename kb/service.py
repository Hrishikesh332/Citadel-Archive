from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
import logging
from typing import Any

from kb.cognee_client import CogneeGateway, CogneePublicClient
from kb.config import CitadelConfig
from kb.filters import PreIngestFilter
from kb.models import FeedbackRequest, FeedbackResult, IngestResult
from kb.source_search import search_github_sync_state
from kb.tags import merge_tags

logger = logging.getLogger(__name__)


class Citadel:
    def __init__(
        self,
        config: CitadelConfig | None = None,
        *,
        cognee: CogneeGateway | None = None,
    ) -> None:
        self.config = config or CitadelConfig.from_env()
        self.cognee = cognee or CogneePublicClient()
        self.filter = PreIngestFilter(
            min_chars=self.config.min_chars,
            exclude_patterns=self.config.exclude_patterns,
        )
        self._seen_hashes: set[str] = set()

    def _default_session_for_dataset(self, dataset: str) -> str:
        if dataset == self.config.github_sync_dataset:
            return self.config.github_sync_session
        return self.config.default_session

    @classmethod
    def from_env(cls) -> "Citadel":
        return cls(CitadelConfig.from_env())

    async def ingest(
        self,
        data: str,
        *,
        dataset: str | None = None,
        tags: Iterable[str] | None = None,
        session_id: str | None = None,
    ) -> IngestResult:
        target_dataset = dataset or self.config.default_dataset
        merged_tags = merge_tags(self.config.default_tags, tags)
        decision = self.filter.check(data)
        if not decision.accepted:
            logger.info(
                "Ingest rejected for dataset %s: %s", target_dataset, decision.reason
            )
            return IngestResult(False, decision.reason, target_dataset, merged_tags)

        content_hash = sha256(data.encode("utf-8")).hexdigest()
        if content_hash in self._seen_hashes:
            logger.info(
                "Ingest rejected for dataset %s: duplicate_in_process", target_dataset
            )
            return IngestResult(False, "duplicate_in_process", target_dataset, merged_tags)
        self._seen_hashes.add(content_hash)

        result = await self.cognee.remember(
            data,
            dataset_name=target_dataset,
            session_id=session_id,
            tags=merged_tags,
        )
        return IngestResult(True, "accepted", target_dataset, merged_tags, result)

    async def search(
        self,
        query: str,
        *,
        dataset: str | None = None,
        session_id: str | None = None,
        top_k: int = 10,
    ) -> list[Any]:
        target_dataset = dataset or self.config.default_dataset
        results = await self.cognee.recall(
            query,
            dataset=target_dataset,
            session_id=session_id or self._default_session_for_dataset(target_dataset),
            top_k=top_k,
        )
        if results or target_dataset != self.config.github_sync_dataset:
            return results
        return search_github_sync_state(query, self.config, top_k=top_k)

    async def feedback(self, request: FeedbackRequest) -> FeedbackResult:
        session_id = request.session_id or self.config.default_session
        dataset = request.dataset or self.config.default_dataset
        recorded = await self.cognee.add_feedback(
            session_id=session_id,
            qa_id=request.qa_id,
            score=request.score,
            text=request.text,
        )
        improved = False
        if recorded and self.config.auto_improve:
            await self.cognee.improve(
                dataset=dataset,
                session_ids=[session_id],
                build_global_context_index=self.config.build_global_context_index,
            )
            improved = True
        return FeedbackResult(recorded=recorded, improved=improved)

    async def improve(
        self,
        *,
        dataset: str | None = None,
        session_ids: list[str] | None = None,
    ) -> Any:
        return await self.cognee.improve(
            dataset=dataset or self.config.default_dataset,
            session_ids=session_ids,
            build_global_context_index=self.config.build_global_context_index,
        )
