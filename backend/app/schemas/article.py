from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

class CategoryBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ArticleBase(BaseModel):
    title: str
    content: str
    summary: Optional[str] = None
    tags: Optional[str] = None
    category_id: Optional[int] = None
    is_published: bool = True

class ArticleCreate(ArticleBase):
    pass

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[str] = None
    category_id: Optional[int] = None
    is_published: Optional[bool] = None

class ArticleResponse(ArticleBase):
    id: int
    views_count: int
    helpful_count: int
    unhelpful_count: int
    created_at: datetime
    updated_at: datetime
    category: Optional[CategoryResponse] = None

    class Config:
        from_attributes = True

class ArticleListItem(BaseModel):
    id: int
    title: str
    summary: Optional[str] = None
    tags: Optional[str] = None
    category_name: Optional[str] = None
    views_count: int
    helpful_count: int
    unhelpful_count: int
    created_at: datetime

    class Config:
        from_attributes = True
