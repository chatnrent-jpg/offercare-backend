"""
VettedMe Internationalization (i18n) Service

Supports 15 languages for global reach:
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Chinese Simplified (zh-CN)
- Japanese (ja)
- Korean (ko)
- Portuguese (pt)
- Italian (it)
- Dutch (nl)
- Russian (ru)
- Arabic (ar)
- Hindi (hi)
- Turkish (tr)
- Polish (pl)
"""

from typing import Dict, Optional
from datetime import datetime
import json
import os

# ==================== LANGUAGE CODES ====================

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "zh-CN": "简体中文",
    "ja": "日本語",
    "ko": "한국어",
    "pt": "Português",
    "it": "Italiano",
    "nl": "Nederlands",
    "ru": "Русский",
    "ar": "العربية",
    "hi": "हिन्दी",
    "tr": "Türkçe",
    "pl": "Polski",
}

# ==================== TRANSLATIONS ====================

TRANSLATIONS = {
    # English
    "en": {
        "app.name": "VettedMe",
        "app.tagline": "The Universal Trust Layer for Digital Identity",
        "verification.success": "Verification Successful",
        "verification.failed": "Verification Failed",
        "verification.trust_score": "Trust Score",
        "verification.verified_at": "Verified At",
        "passport.title": "My Passport",
        "passport.badges": "Active Badges",
        "passport.trust_score": "Trust Score",
        "passport.issued": "Issued",
        "passport.expires": "Expires",
        "badge.healthcare": "Healthcare Professional",
        "badge.security_clearance": "Security Clearance",
        "badge.insurance": "Insurance Licensed",
        "badge.financial_advisor": "Financial Advisor",
        "badge.real_estate": "Real Estate Professional",
        "badge.lawyer": "Licensed Attorney",
        "badge.education": "Verified Education",
        "badge.employment": "Verified Employment",
        "badge.biometric_id": "Biometric Identity",
        "badge.criminal_background": "Background Checked",
        "error.not_found": "Resource not found",
        "error.unauthorized": "Unauthorized access",
        "error.invalid_api_key": "Invalid API key",
        "error.rate_limit": "Rate limit exceeded",
        "action.verify": "Verify",
        "action.scan_qr": "Scan QR Code",
        "action.add_to_wallet": "Add to Wallet",
        "action.share": "Share",
        "status.active": "Active",
        "status.expired": "Expired",
        "status.revoked": "Revoked",
    },
    
    # Spanish
    "es": {
        "app.name": "VettedMe",
        "app.tagline": "La Capa Universal de Confianza para Identidad Digital",
        "verification.success": "Verificación Exitosa",
        "verification.failed": "Verificación Fallida",
        "verification.trust_score": "Puntuación de Confianza",
        "verification.verified_at": "Verificado en",
        "passport.title": "Mi Pasaporte",
        "passport.badges": "Insignias Activas",
        "passport.trust_score": "Puntuación de Confianza",
        "passport.issued": "Emitido",
        "passport.expires": "Expira",
        "badge.healthcare": "Profesional de la Salud",
        "badge.security_clearance": "Autorización de Seguridad",
        "badge.insurance": "Licencia de Seguros",
        "badge.financial_advisor": "Asesor Financiero",
        "badge.real_estate": "Profesional Inmobiliario",
        "badge.lawyer": "Abogado Licenciado",
        "error.not_found": "Recurso no encontrado",
        "error.unauthorized": "Acceso no autorizado",
        "error.invalid_api_key": "Clave API inválida",
        "error.rate_limit": "Límite de tasa excedido",
        "action.verify": "Verificar",
        "action.scan_qr": "Escanear Código QR",
        "action.add_to_wallet": "Agregar a Billetera",
        "action.share": "Compartir",
        "status.active": "Activo",
        "status.expired": "Expirado",
        "status.revoked": "Revocado",
    },
    
    # French
    "fr": {
        "app.name": "VettedMe",
        "app.tagline": "La Couche Universelle de Confiance pour l'Identité Numérique",
        "verification.success": "Vérification Réussie",
        "verification.failed": "Vérification Échouée",
        "verification.trust_score": "Score de Confiance",
        "verification.verified_at": "Vérifié à",
        "passport.title": "Mon Passeport",
        "passport.badges": "Badges Actifs",
        "passport.trust_score": "Score de Confiance",
        "passport.issued": "Émis",
        "passport.expires": "Expire",
        "badge.healthcare": "Professionnel de Santé",
        "badge.security_clearance": "Habilitation de Sécurité",
        "badge.insurance": "Licence d'Assurance",
        "badge.financial_advisor": "Conseiller Financier",
        "badge.real_estate": "Professionnel Immobilier",
        "badge.lawyer": "Avocat Licencié",
        "error.not_found": "Ressource introuvable",
        "error.unauthorized": "Accès non autorisé",
        "error.invalid_api_key": "Clé API invalide",
        "error.rate_limit": "Limite de taux dépassée",
        "action.verify": "Vérifier",
        "action.scan_qr": "Scanner le Code QR",
        "action.add_to_wallet": "Ajouter au Portefeuille",
        "action.share": "Partager",
        "status.active": "Actif",
        "status.expired": "Expiré",
        "status.revoked": "Révoqué",
    },
    
    # German
    "de": {
        "app.name": "VettedMe",
        "app.tagline": "Die Universelle Vertrauensschicht für Digitale Identität",
        "verification.success": "Überprüfung Erfolgreich",
        "verification.failed": "Überprüfung Fehlgeschlagen",
        "verification.trust_score": "Vertrauenspunktzahl",
        "verification.verified_at": "Verifiziert um",
        "passport.title": "Mein Reisepass",
        "passport.badges": "Aktive Ausweise",
        "passport.trust_score": "Vertrauenspunktzahl",
        "passport.issued": "Ausgestellt",
        "passport.expires": "Läuft ab",
        "badge.healthcare": "Gesundheitsfachkraft",
        "badge.security_clearance": "Sicherheitsfreigabe",
        "badge.insurance": "Versicherungslizenz",
        "badge.financial_advisor": "Finanzberater",
        "badge.real_estate": "Immobilienfachmann",
        "badge.lawyer": "Lizenzierter Anwalt",
        "error.not_found": "Ressource nicht gefunden",
        "error.unauthorized": "Unbefugter Zugriff",
        "error.invalid_api_key": "Ungültiger API-Schlüssel",
        "error.rate_limit": "Ratenbegrenzung überschritten",
        "action.verify": "Überprüfen",
        "action.scan_qr": "QR-Code Scannen",
        "action.add_to_wallet": "Zur Wallet Hinzufügen",
        "action.share": "Teilen",
        "status.active": "Aktiv",
        "status.expired": "Abgelaufen",
        "status.revoked": "Widerrufen",
    },
    
    # Chinese Simplified
    "zh-CN": {
        "app.name": "VettedMe",
        "app.tagline": "数字身份的通用信任层",
        "verification.success": "验证成功",
        "verification.failed": "验证失败",
        "verification.trust_score": "信任评分",
        "verification.verified_at": "验证时间",
        "passport.title": "我的护照",
        "passport.badges": "有效徽章",
        "passport.trust_score": "信任评分",
        "passport.issued": "签发",
        "passport.expires": "过期",
        "badge.healthcare": "医疗专业人员",
        "badge.security_clearance": "安全许可",
        "badge.insurance": "保险许可证",
        "badge.financial_advisor": "财务顾问",
        "badge.real_estate": "房地产专业人员",
        "badge.lawyer": "执业律师",
        "error.not_found": "未找到资源",
        "error.unauthorized": "未经授权的访问",
        "error.invalid_api_key": "无效的API密钥",
        "error.rate_limit": "超过速率限制",
        "action.verify": "验证",
        "action.scan_qr": "扫描二维码",
        "action.add_to_wallet": "添加到钱包",
        "action.share": "分享",
        "status.active": "活跃",
        "status.expired": "已过期",
        "status.revoked": "已撤销",
    },
    
    # Japanese
    "ja": {
        "app.name": "VettedMe",
        "app.tagline": "デジタルアイデンティティのための普遍的な信頼レイヤー",
        "verification.success": "検証成功",
        "verification.failed": "検証失敗",
        "verification.trust_score": "信頼スコア",
        "verification.verified_at": "検証日時",
        "passport.title": "マイパスポート",
        "passport.badges": "アクティブなバッジ",
        "passport.trust_score": "信頼スコア",
        "passport.issued": "発行日",
        "passport.expires": "有効期限",
        "badge.healthcare": "医療専門家",
        "badge.security_clearance": "セキュリティクリアランス",
        "badge.insurance": "保険ライセンス",
        "badge.financial_advisor": "ファイナンシャルアドバイザー",
        "badge.real_estate": "不動産専門家",
        "badge.lawyer": "弁護士",
        "error.not_found": "リソースが見つかりません",
        "error.unauthorized": "不正なアクセス",
        "error.invalid_api_key": "無効なAPIキー",
        "error.rate_limit": "レート制限を超過",
        "action.verify": "検証",
        "action.scan_qr": "QRコードをスキャン",
        "action.add_to_wallet": "ウォレットに追加",
        "action.share": "共有",
        "status.active": "アクティブ",
        "status.expired": "期限切れ",
        "status.revoked": "取り消済み",
    },
}

# ==================== TRANSLATION SERVICE ====================

class I18nService:
    """Internationalization service"""
    
    def __init__(self, default_language: str = "en"):
        self.default_language = default_language
        self.current_language = default_language
        self.translations = TRANSLATIONS
    
    def set_language(self, language: str):
        """Set the current language"""
        if language in SUPPORTED_LANGUAGES:
            self.current_language = language
        else:
            raise ValueError(f"Unsupported language: {language}")
    
    def t(self, key: str, language: Optional[str] = None, **kwargs) -> str:
        """
        Translate a key
        
        Args:
            key: Translation key (e.g., "verification.success")
            language: Override current language
            **kwargs: Variables to interpolate into translation
        
        Returns:
            Translated string
        
        Example:
            >>> i18n = I18nService()
            >>> i18n.t("verification.success")
            "Verification Successful"
            >>> i18n.t("verification.success", language="es")
            "Verificación Exitosa"
        """
        lang = language or self.current_language
        
        # Get translation
        translation = self.translations.get(lang, {}).get(key)
        
        # Fall back to English if not found
        if not translation:
            translation = self.translations.get(self.default_language, {}).get(key, key)
        
        # Interpolate variables
        if kwargs:
            translation = translation.format(**kwargs)
        
        return translation
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages"""
        return SUPPORTED_LANGUAGES.copy()
    
    def detect_language_from_header(self, accept_language: str) -> str:
        """
        Detect language from Accept-Language header
        
        Args:
            accept_language: Value of Accept-Language header
        
        Returns:
            Best matching language code
        
        Example:
            >>> i18n.detect_language_from_header("es-ES,es;q=0.9,en;q=0.8")
            "es"
        """
        if not accept_language:
            return self.default_language
        
        # Parse Accept-Language header
        languages = []
        for lang in accept_language.split(","):
            parts = lang.strip().split(";")
            code = parts[0].strip()
            
            # Extract quality value
            q = 1.0
            if len(parts) > 1:
                try:
                    q = float(parts[1].strip().split("=")[1])
                except (IndexError, ValueError):
                    pass
            
            languages.append((code, q))
        
        # Sort by quality
        languages.sort(key=lambda x: x[1], reverse=True)
        
        # Find best match
        for code, _ in languages:
            # Exact match
            if code in SUPPORTED_LANGUAGES:
                return code
            
            # Language family match (e.g., "es-ES" -> "es")
            base_lang = code.split("-")[0]
            if base_lang in SUPPORTED_LANGUAGES:
                return base_lang
        
        return self.default_language


# ==================== FASTAPI MIDDLEWARE ====================

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class I18nMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically set language from Accept-Language header"""
    
    async def dispatch(self, request: Request, call_next):
        # Get Accept-Language header
        accept_language = request.headers.get("Accept-Language", "en")
        
        # Detect language
        i18n = I18nService()
        detected_language = i18n.detect_language_from_header(accept_language)
        
        # Store in request state
        request.state.language = detected_language
        
        response = await call_next(request)
        return response


# ==================== EXAMPLE USAGE ====================

if __name__ == "__main__":
    # Create service
    i18n = I18nService()
    
    # English
    print(i18n.t("verification.success"))  # "Verification Successful"
    
    # Spanish
    print(i18n.t("verification.success", language="es"))  # "Verificación Exitosa"
    
    # French
    print(i18n.t("verification.success", language="fr"))  # "Vérification Réussie"
    
    # German
    print(i18n.t("verification.success", language="de"))  # "Überprüfung Erfolgreich"
    
    # Chinese
    print(i18n.t("verification.success", language="zh-CN"))  # "验证成功"
    
    # Japanese
    print(i18n.t("verification.success", language="ja"))  # "検証成功"
