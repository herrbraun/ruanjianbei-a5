from app.models.user import AdminProfile, LoginLog, User, VisitorProfile
from app.models.knowledge import (
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeEmbedding,
    RagProfile,
    RagProfileKnowledgeBase,
    RagQueryLog,
    ScenicArea,
)
from app.models.guide import GuideFeedback, GuideMessage, GuideMessageInsight, GuideSession, InsightReportSchedule, ScenicInsightReport
from app.models.avatar import AvatarVariant, DigitalHuman, ScenicAvatarConfig
from app.models.spot import (
    RouteFeedback,
    RoutePlan,
    RouteRecommendationSetting,
    RouteSpot,
    ScenicSpot,
    SpotMediaAsset,
    SpotTag,
    VisitorBehaviorRecord,
)

__all__ = [
    "AdminProfile", "AvatarVariant", "DigitalHuman", "KnowledgeBase", "KnowledgeChunk", "KnowledgeDocument", "KnowledgeEmbedding",
    "GuideFeedback", "GuideMessage", "GuideMessageInsight", "GuideSession", "InsightReportSchedule", "LoginLog", "RagProfile", "RagProfileKnowledgeBase", "RagQueryLog",
    "RouteFeedback", "RoutePlan", "RouteRecommendationSetting", "RouteSpot", "ScenicArea", "ScenicAvatarConfig",
    "ScenicInsightReport", "ScenicSpot", "SpotMediaAsset", "SpotTag", "User", "VisitorBehaviorRecord", "VisitorProfile",
]
