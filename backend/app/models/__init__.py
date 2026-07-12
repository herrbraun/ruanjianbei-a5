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
from app.models.guide import GuideMessage, GuideSession
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
    "GuideMessage", "GuideSession", "LoginLog", "RagProfile", "RagProfileKnowledgeBase", "RagQueryLog",
    "RouteFeedback", "RoutePlan", "RouteRecommendationSetting", "RouteSpot", "ScenicArea", "ScenicAvatarConfig",
    "ScenicSpot", "SpotMediaAsset", "SpotTag", "User", "VisitorBehaviorRecord", "VisitorProfile",
]
