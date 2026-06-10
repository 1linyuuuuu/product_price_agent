from typing import TypedDict, Annotated
import operator


class AnalysisState(TypedDict):
    query: str
    product_name: str
    variants: list
    platforms_new: list[str]
    platforms_used: list[str]
    user_concern: str
    price_data: Annotated[dict, lambda left, right: {**left, **right}]
    history_data: Annotated[dict, lambda left, right: {**left, **right}]
    comparison_report: str
    recommendation: str
    recommend_cards: Annotated[list, operator.add]
    product_images: dict  # {variant_spec: [image_urls]}
    trend_data: dict
    is_multi: bool  # 是否多商品集合
    sub_products: list  # 多商品场景下的子商品列表
    sub_results: list  # 多商品场景下各子商品的结果
    errors: Annotated[list, operator.add]
