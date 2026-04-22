"""
LLM-based impact analysis module.
Provides stub and real provider adapters for generating structured JSON analysis.
"""
import json
import os
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models import LLMImpactAnalysis, RetrievedChunk


class LLMProvider:
    """Base class for LLM providers."""
    
    def analyze(self, 
                ticker: str,
                article_excerpt: str,
                title: str,
                retrieved_context: List[RetrievedChunk]) -> LLMImpactAnalysis:
        """Analyze article and return structured impact analysis."""
        raise NotImplementedError


class StubLLMProvider(LLMProvider):
    """Stub LLM that returns valid JSON responses for testing."""
    
    def analyze(self, 
                ticker: str,
                article_excerpt: str,
                title: str,
                retrieved_context: List[RetrievedChunk]) -> LLMImpactAnalysis:
        """Return deterministic stub response."""
        
        # Determine event type based on keywords in title/excerpt
        combined_text = f"{title} {article_excerpt}".lower()
        
        event_type = "other"
        if any(word in combined_text for word in ["lawsuit", "sued", "court", "legal"]):
            event_type = "lawsuit"
        elif any(word in combined_text for word in ["earnings", "quarterly", "revenue", "profit", "eps"]):
            event_type = "earnings"
        elif any(word in combined_text for word in ["guidance", "outlook", "forecast", "expect"]):
            event_type = "guidance"
        elif any(word in combined_text for word in ["launch", "introduce", "release", "new product"]):
            event_type = "product_launch"
        elif any(word in combined_text for word in ["regulation", "regulatory", "sec", "investigation"]):
            event_type = "regulatory"
        
        # Determine sentiment-based impact
        positive_words = ["surge", "strong", "record", "beat", "outperform", "grow", "expand"]
        negative_words = ["fall", "decline", "miss", "weak", "lawsuit", "investigate", "risk", "loss"]
        
        positive_score = sum(1 for word in positive_words if word in combined_text)
        negative_score = sum(1 for word in negative_words if word in combined_text)
        
        impact_score = min(1.0, max(-1.0, (positive_score - negative_score) * 0.3))
        
        # Build citations from retrieved context
        citations = []
        for i, chunk in enumerate(retrieved_context[:3]):
            citations.append({
                "layer": chunk.layer,
                "source_id": chunk.source_id,
                "why": f"Provides context on {chunk.layer} for {ticker}"
            })
        
        return LLMImpactAnalysis(
            ticker=ticker,
            event_type=event_type,
            is_new_information=len(retrieved_context) < 3,  # Few results means new info
            impact_score=impact_score,
            horizon="swing" if abs(impact_score) > 0.5 else "intraday",
            severity="high" if abs(impact_score) > 0.7 else "med" if abs(impact_score) > 0.3 else "low",
            confidence=0.6 + (len(retrieved_context) * 0.05),  # More context = more confidence
            risk_flags=["low_quality_source"] if "rumor" in combined_text else [],
            contradiction_flags=["none"],
            summary=f"{event_type.replace('_', ' ').title()} event detected for {ticker}. Impact: {impact_score:.2f}",
            evidence=article_excerpt[:200],
            citations=citations
        )


class OpenAIProvider(LLMProvider):
    """OpenAI ChatGPT-based LLM provider."""
    
    SYSTEM_PROMPT = """You are a financial analyst specialized in extracting and analyzing news impact.
You will be given:
1) A news article excerpt
2) Retrieved context about the company (profile, recent events)
3) A ticker symbol

Your task is to output STRICT JSON analysis with these fields:
- ticker: string
- event_type: one of [lawsuit, earnings, guidance, product_launch, regulatory, macro, other]
- is_new_information: boolean
- impact_score: float between -1.0 and 1.0
- horizon: one of [intraday, swing, long]
- severity: one of [low, med, high]
- confidence: float between 0 and 1
- risk_flags: list of any of [rumor, low_quality_source, ambiguous, already_priced_in]
- contradiction_flags: list of any of [conflicts_with_guidance, conflicts_with_state, none]
- summary: 1-2 sentence summary
- evidence: 1 short excerpt from the article
- citations: list of {layer, source_id, why} referencing provided context

IMPORTANT RULES:
1) Output ONLY valid JSON, no other text
2) If uncertain, set low confidence and is_new_information=false
3) Match citations to provided context layers (profile/state/event)
4) Do NOT recommend trading actions; only analysis
5) If the news contradicts recent guidance or state, mark in contradiction_flags
"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        # Would import openai client here
    
    def analyze(self, 
                ticker: str,
                article_excerpt: str,
                title: str,
                retrieved_context: List[RetrievedChunk]) -> LLMImpactAnalysis:
        """Call OpenAI API to analyze article."""
        raise NotImplementedError("OpenAI integration not yet implemented for MVP. Use StubLLMProvider.")


class GeminiProvider(LLMProvider):
    """Google Gemini-based LLM provider using google-genai SDK."""

    SYSTEM_PROMPT = """You are a financial analyst specialized in extracting and analyzing news impact on stocks.
You will be given:
1) A news article excerpt
2) Retrieved context about the company (profile, recent events)
3) A ticker symbol

Your task is to produce a structured JSON analysis with these fields:
- ticker: string (the stock ticker being analyzed)
- event_type: one of [lawsuit, earnings, guidance, product_launch, regulatory, macro, other]
- is_new_information: boolean (true if this is genuinely new, not already known)
- impact_score: float between -1.0 (very negative) and 1.0 (very positive)
- horizon: one of [intraday, swing, long]
- severity: one of [low, med, high]
- confidence: float between 0 and 1 (your confidence in this analysis)
- risk_flags: list of any applicable flags: [rumor, low_quality_source, ambiguous, already_priced_in] (empty list if none)
- contradiction_flags: list of any applicable flags: [conflicts_with_guidance, conflicts_with_state, none]
- summary: 1-2 sentence summary of the impact
- evidence: 1 short excerpt from the article supporting the analysis
- citations: list of {layer, source_id, why} referencing provided context (can be empty)

IMPORTANT RULES:
1) Be precise with impact_score — use the full range from -1.0 to 1.0
2) If uncertain, set low confidence and is_new_information=false
3) If the news contradicts recent guidance or state, mark in contradiction_flags
4) Do NOT recommend trading actions; only analyze the impact
5) For Indian market stocks, use NSE ticker symbols
"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key required. Set GEMINI_API_KEY in .env")

        from google import genai
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.5-flash"
        print(f"[Gemini] Initialized with model: {self.model}")

    def analyze(self,
                ticker: str,
                article_excerpt: str,
                title: str,
                retrieved_context: List[RetrievedChunk]) -> LLMImpactAnalysis:
        """Call Gemini API to analyze article and return structured impact analysis."""

        # Build the user prompt
        user_prompt = create_analysis_prompt(
            ticker=ticker,
            title=title,
            article_excerpt=article_excerpt,
            retrieved_context=retrieved_context,
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=f"{self.SYSTEM_PROMPT}\n\n{user_prompt}",
                config={
                    "response_mime_type": "application/json",
                },
            )

            # Parse JSON response manually
            analysis = parse_llm_response(response.text)
            if analysis:
                print(f"[Gemini] Analysis for {ticker}: "
                      f"impact={analysis.impact_score:+.2f}, "
                      f"event={analysis.event_type}, "
                      f"confidence={analysis.confidence:.2f}")
                return analysis
            else:
                print(f"[Gemini] Failed to parse response for {ticker}, "
                      f"falling back to stub")
                return StubLLMProvider().analyze(
                    ticker, article_excerpt, title, retrieved_context
                )

        except Exception as e:
            print(f"[Gemini] API call failed for {ticker}: {e}")
            print(f"[Gemini] Falling back to stub analysis")
            return StubLLMProvider().analyze(
                ticker, article_excerpt, title, retrieved_context
            )


class GrokProvider(LLMProvider):
    """xAI Grok-based LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROK_API_KEY")
        if not self.api_key:
            raise ValueError("Grok API key required")
    
    def analyze(self, 
                ticker: str,
                article_excerpt: str,
                title: str,
                retrieved_context: List[RetrievedChunk]) -> LLMImpactAnalysis:
        """Call Grok API to analyze article."""
        raise NotImplementedError("Grok integration not yet implemented for MVP. Use StubLLMProvider.")


# Global LLM provider instance
_llm_provider: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """Get or create the global LLM provider.
    
    Auto-selects GeminiProvider if GEMINI_API_KEY is set,
    otherwise falls back to StubLLMProvider.
    """
    global _llm_provider
    if _llm_provider is None:
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            try:
                _llm_provider = GeminiProvider(api_key=gemini_key)
                print("[LLM] Using GeminiProvider for analysis")
            except Exception as e:
                print(f"[LLM] Failed to init GeminiProvider: {e}")
                print("[LLM] Falling back to StubLLMProvider")
                _llm_provider = StubLLMProvider()
        else:
            print("[LLM] No Gemini API key found, using StubLLMProvider")
            _llm_provider = StubLLMProvider()
    return _llm_provider


def set_llm_provider(provider: LLMProvider):
    """Set the global LLM provider."""
    global _llm_provider
    _llm_provider = provider


def format_context_for_llm(retrieved_chunks: List[RetrievedChunk]) -> str:
    """Format retrieved context for inclusion in LLM prompt."""
    if not retrieved_chunks:
        return "No prior context found."
    
    context_text = "Retrieved Context:\n"
    for i, chunk in enumerate(retrieved_chunks, 1):
        context_text += f"\n[{i}] Layer: {chunk.layer} | Source: {chunk.source_id}\n"
        context_text += f"Snippet: {chunk.snippet[:200]}...\n"
    
    return context_text


def create_analysis_prompt(ticker: str,
                          title: str,
                          article_excerpt: str,
                          retrieved_context: List[RetrievedChunk]) -> str:
    """Create the full prompt for LLM analysis."""
    
    context_str = format_context_for_llm(retrieved_context)
    
    prompt = f"""
TICKER: {ticker}
ARTICLE TITLE: {title}

ARTICLE EXCERPT:
{article_excerpt}

{context_str}

Please analyze this article and provide a JSON response following the schema specified in your system prompt.
Output ONLY the JSON, no explanations.
"""
    
    return prompt


def parse_llm_response(response_text: str) -> Optional[LLMImpactAnalysis]:
    """Parse and validate LLM response JSON."""
    try:
        # Extract JSON from response (might have extra text)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            return None
        
        json_str = json_match.group(0)
        data = json.loads(json_str)
        
        # Validate with Pydantic
        analysis = LLMImpactAnalysis(**data)
        return analysis
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Failed to parse LLM response: {e}")
        return None
