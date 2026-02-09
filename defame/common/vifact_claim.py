from typing import Optional, Any, Dict
from defame.common.claim import Claim
from defame.common.content import Content

class ViFactClaim(Claim):
    """
    Mở rộng Claim cho ViFactCheck:
    """
    
    def __init__(self,
        *args,
        id: str | int | None = None,
        context: Content = None,
        scope: tuple[int, int] = None,
        **kwargs
    ):
        super().__init__(*args, id=id, context=context, 
                 scope=scope, **kwargs)