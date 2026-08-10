"""Embedding generation for movie semantic search using sentence-transformers."""

import json
from typing import List, Dict
from sentence_transformers import SentenceTransformer
import numpy as np


class EmbeddingGenerator:
    """Generates embeddings for movie data using sentence-transformers.
    
    This class uses the all-MiniLM-L6-v2 model which:
    - Runs locally (no API key needed)
    - Produces 384-dimensional embeddings
    - Is free and fast
    - Works well for semantic similarity tasks
    """
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """Initialize embedding generator.
        
        Args:
            model_name: Name of the sentence-transformers model to use.
                       Default: all-MiniLM-L6-v2 (384 dimensions)
        """
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        print(f"Model loaded. Embedding dimension: {self.embedding_dim}")
    
    def create_movie_text(self, movie_data: Dict) -> str:
        """Create a text representation of movie for embedding.
        
        Args:
            movie_data: Movie data dictionary
        
        Returns:
            Text string combining key movie attributes
        """
        parts = []
        
        # Title
        if movie_data.get("title"):
            parts.append(f"Title: {movie_data['title']}")
        
        # Overview/plot
        if movie_data.get("overview"):
            parts.append(f"Plot: {movie_data['overview']}")
        
        # Genres
        genres = movie_data.get("genres", [])
        if genres:
            if isinstance(genres, str):
                genres = json.loads(genres)
            genre_names = [g["name"] for g in genres if "name" in g]
            if genre_names:
                parts.append(f"Genres: {', '.join(genre_names)}")
        
        # Keywords
        keywords = movie_data.get("keywords", [])
        if keywords:
            if isinstance(keywords, str):
                keywords = json.loads(keywords)
            keyword_names = [k["name"] for k in keywords if "name" in k]
            if keyword_names:
                parts.append(f"Keywords: {', '.join(keyword_names[:15])}")
        
        # Cast
        cast = movie_data.get("cast_info", [])
        if cast:
            if isinstance(cast, str):
                cast = json.loads(cast)
            cast_names = [c["name"] for c in cast[:5] if "name" in c]
            if cast_names:
                parts.append(f"Cast: {', '.join(cast_names)}")
        
        # Runtime
        if movie_data.get("runtime"):
            parts.append(f"Runtime: {movie_data['runtime']} minutes")
        
        return " | ".join(parts)
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector as a list of floats
        """
        embedding = self.model.encode([text])[0]
        return embedding.tolist()
    
    def generate_movie_embedding(self, movie_data: Dict) -> List[float]:
        """Generate embedding for a movie.
        
        Args:
            movie_data: Movie data dictionary
        
        Returns:
            Embedding vector as a list of floats
        """
        text = self.create_movie_text(movie_data)
        return self.generate_embedding(text)
    
    def generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for a search query.
        
        Args:
            query: Search query text
        
        Returns:
            Embedding vector as a list of floats
        """
        return self.generate_embedding(query)
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model.
        
        Returns:
            Embedding dimension (384 for all-MiniLM-L6-v2)
        """
        return self.embedding_dim
