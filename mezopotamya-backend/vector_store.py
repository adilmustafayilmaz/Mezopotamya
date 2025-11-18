"""
Vector Store Module for Qdrant Integration
Handles Qdrant client, collection management, and vector operations
"""

import os
from typing import List, Dict, Optional, Any
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, 
    MatchValue, CollectionStatus
)
from qdrant_client.http import models


class VectorStore:
    """Manages vector storage and retrieval using Qdrant"""
    
    def __init__(self, host: str = None, port: int = None, api_key: str = None, collection_name: str = "tourism_documents"):
        """
        Initialize Qdrant client
        
        Args:
            host: Qdrant host (default from env)
            port: Qdrant port (default from env, not used for cloud)
            api_key: Qdrant API key (for Qdrant Cloud)
            collection_name: Name of the collection
        """
        self.host = host or os.getenv("QDRANT_HOST", "localhost")
        self.port = port or int(os.getenv("QDRANT_PORT", "6333"))
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.collection_name = collection_name
        
        # Initialize Qdrant client
        try:
            # Check if using Qdrant Cloud (URL with https)
            if self.api_key or (self.host.startswith("https://") or ".qdrant.io" in self.host or ".qdrant.cloud" in self.host):
                # Qdrant Cloud connection
                url = self.host if self.host.startswith("http") else f"https://{self.host}"
                self.client = QdrantClient(url=url, api_key=self.api_key)
            else:
                # Local Qdrant connection
                self.client = QdrantClient(host=self.host, port=self.port)
        except Exception as e:
            print(f"Warning: Could not connect to Qdrant at {self.host}:{self.port}: {e}")
            self.client = None
    
    def ensure_collection(self, vector_size: int = 384) -> bool:
        """
        Ensure collection exists, create if it doesn't
        
        Args:
            vector_size: Size of vectors (384 for multilingual MiniLM)
            
        Returns:
            True if collection exists or was created successfully
        """
        if not self.client:
            return False
        
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                # Create collection
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE
                    )
                )
                print(f"Created Qdrant collection: {self.collection_name}")
                return True
            else:
                # Verify collection is ready
                collection_info = self.client.get_collection(self.collection_name)
                if collection_info.status == CollectionStatus.GREEN:
                    return True
                return False
        except Exception as e:
            print(f"Error ensuring collection: {e}")
            return False
    
    def add_documents(self, chunks: List[Dict], document_id: int = None) -> bool:
        """
        Add document chunks to Qdrant
        
        Args:
            chunks: List of chunk dictionaries with 'text', 'embedding', 'metadata'
            document_id: Optional document ID to associate with chunks
            
        Returns:
            True if successful
        """
        if not self.client or not chunks:
            return False
        
        if not self.ensure_collection():
            return False
        
        try:
            points = []
            for i, chunk in enumerate(chunks):
                if 'embedding' not in chunk:
                    continue
                
                # Create point ID (use document_id and chunk_index if available)
                point_id = chunk.get('vector_id')
                if not point_id:
                    chunk_idx = chunk.get('chunk_index', i)
                    if document_id:
                        point_id = document_id * 10000 + chunk_idx
                    else:
                        point_id = hash(chunk['text']) % (10 ** 10)
                
                # Prepare payload (metadata)
                payload = {
                    'text': chunk['text'],
                    'chunk_index': chunk.get('chunk_index', i),
                    **chunk.get('metadata', {})
                }
                
                if document_id:
                    payload['document_id'] = document_id
                
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=chunk['embedding'],
                        payload=payload
                    )
                )
            
            # Batch upsert
            if points:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                print(f"Added {len(points)} chunks to Qdrant")
                return True
            
            return False
        except Exception as e:
            print(f"Error adding documents to Qdrant: {e}")
            return False
    
    def search(self, query_vector: List[float], limit: int = 5, 
               filter_dict: Dict = None) -> List[Dict]:
        """
        Search for similar vectors in Qdrant
        
        Args:
            query_vector: Query embedding vector
            limit: Number of results to return
            filter_dict: Optional metadata filters (e.g., {'type': 'itinerary'})
            
        Returns:
            List of search results with text, metadata, and score
        """
        if not self.client:
            return []
        
        try:
            # Build filter if provided
            search_filter = None
            if filter_dict:
                conditions = []
                for key, value in filter_dict.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
                if conditions:
                    search_filter = Filter(must=conditions)
            
            # Perform search
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=search_filter
            )
            
            # Format results
            results = []
            for result in search_results:
                results.append({
                    'text': result.payload.get('text', ''),
                    'score': result.score,
                    'metadata': {k: v for k, v in result.payload.items() if k != 'text'},
                    'id': result.id
                })
            
            return results
        except Exception as e:
            print(f"Error searching Qdrant: {e}")
            return []
    
    def delete_document(self, document_id: int) -> bool:
        """
        Delete all chunks associated with a document
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            True if successful
        """
        if not self.client:
            return False
        
        try:
            # Delete points with matching document_id
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="document_id",
                                match=MatchValue(value=document_id)
                            )
                        ]
                    )
                )
            )
            print(f"Deleted document {document_id} from Qdrant")
            return True
        except Exception as e:
            print(f"Error deleting document from Qdrant: {e}")
            return False
    
    def get_collection_info(self) -> Dict:
        """Get information about the collection"""
        if not self.client:
            return {}
        
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                'name': self.collection_name,
                'points_count': collection_info.points_count,
                'vectors_count': collection_info.vectors_count,
                'status': collection_info.status.value if collection_info.status else 'unknown'
            }
        except Exception as e:
            print(f"Error getting collection info: {e}")
            return {}
    
    def is_connected(self) -> bool:
        """Check if Qdrant client is connected"""
        if not self.client:
            return False
        
        try:
            self.client.get_collections()
            return True
        except:
            return False

