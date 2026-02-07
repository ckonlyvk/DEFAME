"""Vietnamese text preprocessing utilities for claim extraction and fact-checking.

This module provides Vietnamese-specific text processing using the underthesea library,
including tokenization, sentence segmentation, stopword removal, and text normalization.
"""

from typing import List, Optional
import re


class VietnamesePreprocessor:
    """Vietnamese text preprocessing utilities."""
    
    # Vietnamese stopwords - common words to filter out
    # Based on common Vietnamese function words and particles
    STOPWORDS = {
        # Conjunctions and particles
        'và', 'hoặc', 'hay', 'nhưng', 'mà', 'nên', 'vì', 'do', 'nếu', 'thì',
        
        # Prepositions
        'của', 'cho', 'với', 'để', 'từ', 'theo', 'về', 'tại', 'trong', 'ngoài',
        'trên', 'dưới', 'sau', 'trước', 'giữa', 'bên', 'cùng',
        
        # Articles and determiners
        'các', 'những', 'mọi', 'một', 'cái', 'chiếc', 'con',
        
        # Pronouns
        'này', 'đó', 'kia', 'nào', 'đây', 'đấy',
        
        # Copula and auxiliaries
        'là', 'có', 'được', 'bị', 'bởi', 'đã', 'sẽ', 'đang', 'vẫn', 'còn',
        
        # Others
        'không', 'chưa', 'rằng', 'đến', 'ra', 'vào', 'lên', 'xuống', 'qua',
        'rất', 'lắm', 'quá', 'hơn', 'nhất', 'cũng', 'thêm', 'nữa'
    }
    
    @staticmethod
    def tokenize(text: str, format: str = 'text') -> List[str]:
        """
        Tokenize Vietnamese text into words using underthesea.
        
        Args:
            text: Vietnamese text to tokenize
            format: 'text' returns space-separated string, 
                    'list' returns list of tokens
        
        Returns:
            Tokenized text as string or list of tokens
            
        Example:
            >>> tokenize("Việt Nam là một quốc gia", format='list')
            ['Việt_Nam', 'là', 'một', 'quốc_gia']
        """
        try:
            from underthesea import word_tokenize
            result = word_tokenize(text, format=format)
            return result
        except ImportError:
            # Fallback if underthesea not installed
            import warnings
            warnings.warn("underthesea not installed. Using simple word splitting. "
                         "Install with: pip install underthesea")
            if format == 'list':
                return text.split()
            return text
    
    @staticmethod
    def segment_sentences(text: str) -> List[str]:
        """
        Split text into sentences using Vietnamese-aware segmentation.
        
        Args:
            text: Vietnamese text to segment
        
        Returns:
            List of sentences
            
        Example:
            >>> segment_sentences("Đây là câu đầu. Đây là câu thứ hai!")
            ['Đây là câu đầu.', 'Đây là câu thứ hai!']
        """
        try:
            from underthesea import sent_tokenize
            return sent_tokenize(text)
        except ImportError:
            # Fallback: simple regex-based sentence splitting
            import warnings
            warnings.warn("underthesea not installed. Using simple sentence splitting. "
                         "Install with: pip install underthesea")
            sentences = re.split(r'[.!?]+', text)
            return [s.strip() for s in sentences if s.strip()]
    
    @staticmethod
    def remove_stopwords(tokens: List[str]) -> List[str]:
        """
        Remove Vietnamese stopwords from token list.
        
        Args:
            tokens: List of word tokens
        
        Returns:
            Filtered token list with stopwords removed
            
        Example:
            >>> remove_stopwords(['Việt_Nam', 'là', 'một', 'quốc_gia'])
            ['Việt_Nam', 'quốc_gia']
        """
        return [token for token in tokens 
                if token.lower() not in VietnamesePreprocessor.STOPWORDS]
    
    @staticmethod
    def normalize(text: str, 
                  lowercase: bool = True,
                  remove_punctuation: bool = False) -> str:
        """
        Normalize Vietnamese text.
        
        Args:
            text: Text to normalize
            lowercase: Convert to lowercase
            remove_punctuation: Remove punctuation marks
        
        Returns:
            Normalized text
            
        Example:
            >>> normalize("  VIỆT   NAM   ", lowercase=True)
            'việt nam'
        """
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', text.strip())
        
        if lowercase:
            normalized = normalized.lower()
        
        if remove_punctuation:
            # Keep Vietnamese characters, numbers, and spaces
            # Vietnamese alphabet includes: a-z and special characters with diacritics
            normalized = re.sub(
                r'[^\w\sàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]', 
                '', 
                normalized
            )
        
        return normalized
    
    @classmethod
    def preprocess_for_claim_extraction(cls, text: str) -> dict:
        """
        Complete preprocessing pipeline for claim extraction.
        
        This method applies the full preprocessing pipeline suitable for
        extracting claims from Vietnamese news articles.
        
        Args:
            text: Vietnamese text (e.g., news article)
        
        Returns:
            Dictionary containing:
                - sentences: List of segmented sentences
                - normalized: Normalized full text
                - tokens: Tokenized text (as list)
                - filtered_tokens: Tokens with stopwords removed
                
        Example:
            >>> result = preprocess_for_claim_extraction("Việt Nam có 95 triệu dân. Thủ đô là Hà Nội.")
            >>> len(result['sentences'])
            2
        """
        # Normalize text first
        normalized = cls.normalize(text, lowercase=False, remove_punctuation=False)
        
        # Segment into sentences
        sentences = cls.segment_sentences(normalized)
        
        # Tokenize
        tokens = cls.tokenize(normalized, format='list')
        
        # Remove stopwords
        filtered_tokens = cls.remove_stopwords(tokens)
        
        return {
            'sentences': sentences,
            'normalized': normalized,
            'tokens': tokens,
            'filtered_tokens': filtered_tokens
        }


# Convenience functions for easier imports
def tokenize(text: str, format: str = 'text') -> List[str]:
    """Convenience wrapper for VietnamesePreprocessor.tokenize()"""
    return VietnamesePreprocessor.tokenize(text, format)


def segment_sentences(text: str) -> List[str]:
    """Convenience wrapper for VietnamesePreprocessor.segment_sentences()"""
    return VietnamesePreprocessor.segment_sentences(text)


def remove_stopwords(tokens: List[str]) -> List[str]:
    """Convenience wrapper for VietnamesePreprocessor.remove_stopwords()"""
    return VietnamesePreprocessor.remove_stopwords(tokens)


def normalize(text: str, lowercase: bool = True, remove_punctuation: bool = False) -> str:
    """Convenience wrapper for VietnamesePreprocessor.normalize()"""
    return VietnamesePreprocessor.normalize(text, lowercase, remove_punctuation)


def preprocess_for_claim_extraction(text: str) -> dict:
    """Convenience wrapper for VietnamesePreprocessor.preprocess_for_claim_extraction()"""
    return VietnamesePreprocessor.preprocess_for_claim_extraction(text)
