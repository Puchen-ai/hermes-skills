---
name: shop-spider-adapter-extension
description: 深入讲解如何给 shop-spider 新增一个平台 adapter(parser + fetcher + 注册)
---

# 新增平台 Adapter 深入指南

SKILL.md 末尾给了 3 步概要;本文件展开实现细节,适用于 1688 / 亚马逊中国 / 唯品会 / 苏宁易购 等新平台。

## 1. 先确认 ToS 与可抓性

**别先写代码**。每个平台先回答:

| 检查项 | 通过标准 | 否决动作 |
|---|---|---|
| `robots.txt` 是否允许搜索结果页 | `Allow: /search*` 类条目 | 改用官方开放 API |
| 列表页是否纯 JS 渲染 | `view-source:` 看不到商品节点 | 必须先有 Playwright fetcher(本 skill 未实现) |
| 价格是否需登录态 | 未登录访问,价格字段在 HTML 里 | 排除,本 skill 不做登录态抓取 |
| 是否有官方开放 API | 有商品搜索/详情 API | 优先 API;实在没有再 HTML 解析 |

只有以上全过才动手。

## 2. Adapter 接口契约

`src/spider/shop_site_adapter.py` 定义了 `ShopSiteAdapter` Protocol(伪代码):

```python
class ShopSiteAdapter(Protocol):
    platform: str  # 例: "jd" / "1688"

    def search_urls(self, keyword: str, page: int = 1, **kwargs) -> list[str]: ...
    def parse_search_list(self, html: str, keyword: str, **kwargs) -> list[Product]: ...
    def parse_product_detail(self, html: str, url: str, **kwargs) -> Product: ...
    # 可选(美团类):
    def parse_shop(self, html: str, url: str) -> Shop: ...
    def parse_deal(self, html: str, url: str) -> Deal: ...
```

**必须实现**:前 3 个。**建议实现**:`parse_product_detail`(否则监控流程取不到当前价)。

## 3. 文件结构(以 `xxx_parser.py` 为例)

```python
# src/spider/shop_parsers/xxx_parser.py
from __future__ import annotations
import re, json
from decimal import Decimal
from bs4 import BeautifulSoup

from spider.shop_models import Product, PriceRecord
from spider.shop_site_adapter import ShopSiteAdapter


class XxxAdapter:
    platform = "xxx"

    # ----- URL 构造 -----
    def search_urls(self, keyword: str, page: int = 1, **kwargs) -> list[str]:
        # 例: page=1 -> 单 URL; 多页 -> [url_p1, url_p2, ...]
        kw = quote(keyword)
        return [f"https://search.xxx.com/?q={kw}&p={page}"]

    # ----- 列表解析 -----
    def parse_search_list(self, html: str, keyword: str, **kwargs) -> list[Product]:
        soup = BeautifulSoup(html, "lxml")
        items = soup.select("div.product-item")  # 用真实站点 selector
        products = []
        for el in items:
            try:
                products.append(self._parse_one(el, keyword))
            except (ValueError, AttributeError):
                continue  # 缺字段静默跳过,不要 raise
        return products

    def _parse_one(self, el, keyword: str) -> Product:
        return Product(
            platform=self.platform,
            sku_id=el["data-sku"],
            title=el.select_one(".title").text.strip(),
            url="https:" + el.select_one("a")["href"],
            price=Decimal(el.select_one(".price").text.strip().replace("¥", "")),
            shop_name=el.select_one(".shop").text.strip(),
            # 其余字段留空即可,__post_init__ 只校验必填
        )

    # ----- 详情解析 -----
    def parse_product_detail(self, html: str, url: str, **kwargs) -> Product:
        soup = BeautifulSoup(html, "lxml")
        # 通常需要从 <script> pageData JSON 里挖价格(参考 jd_parser._extract_json_prices)
        ...
        return Product(...)
```

## 4. 必备规范(否则进不去 main.py)

1. **`platform` 必须唯一** — 检查 `shop_parsers/__init__.py` 里现有值,不要撞 `jd/taobao/meituan/pdd`。
2. **价格统一 `Decimal` 字符串** — 绝不要返回 `float` 或 `int`,会丢精度且触发反爬单位混淆(参见 SKILL.md Pitfalls #2, Anti-patterns AP7)。
3. **缺字段跳过** — 列表里某条商品价格/标题缺失,**continue**,不要 raise;这保证一批数据里有残次也不全军覆没。
4. **不在 parser 里发请求** — `parse_*` 只接 HTML 字符串,网络层在 `StealthFetcher` / `HttpFetcher`。
5. **`__post_init__` 别绕过** — Product/PriceRecord 都有字段校验;若某个字段必填但本平台没有,加 Optional 并在 model 改默认值,不要 monkey-patch。

## 5. 注册到 CLI

```python
# src/spider/shop_parsers/__init__.py
from .xxx_parser import XxxAdapter
__all__ = [..., "XxxAdapter"]
```

```python
# main.py 找到 _shop_adapter() factory,加映射:
def _shop_adapter(platform: str):
    return {
        "jd": JdAdapter,
        "taobao": TaobaoAdapter,
        "meituan": MeituanAdapter,
        "pdd": PddAdapter,
        "xxx": XxxAdapter,  # 新增
    }[platform]
```

之后 `python3.8 main.py shop crawl --platform xxx --keyword "..."` 就直接能用。

## 6. 写 fixture + 单测(必做)

```python
# tests/fixtures_xxx.py
XXX_SEARCH_HTML_HEADPHONES = """
<html><body>
  <div class="product-item" data-sku="X001">
    <a href="//item.xxx.com/X001"><div class="title">蓝牙耳机</div></a>
    <div class="price">¥199.00</div>
    <div class="shop">X 旗舰店</div>
  </div>
</body></html>
"""

# tests/test_xxx_parser.py
from spider.shop_parsers import XxxAdapter
from tests.fixtures_xxx import XXX_SEARCH_HTML_HEADPHONES

def test_parse_list_min_count():
    out = XxxAdapter().parse_search_list(XXX_SEARCH_HTML_HEADPHONES, "蓝牙")
    assert len(out) >= 1
    p = out[0]
    assert p.platform == "xxx"
    assert p.sku_id == "X001"
    assert str(p.price) == "199.00"
```

## 7. 完整检查清单

新增一个平台,提交前过一遍:

- [ ] `robots.txt` 允许
- [ ] 价格字段非空(列表 + 详情都要测)
- [ ] 多页 `search_urls(page=N)` 返回 N 个 URL
- [ ] `platform` 字符串未撞名
- [ ] `from decimal import Decimal` 且 `price=Decimal("...")`(不是 int/float)
- [ ] 列表解析里缺字段 → 跳过而非崩溃
- [ ] 注册到 `shop_parsers/__init__.py` 和 `main.py:_shop_adapter()`
- [ ] `tests/test_xxx_parser.py` 至少 5 个 case(列表 / 详情 / 空 HTML / 缺字段 / 多页)
- [ ] `tests/fixtures_xxx.py` 离线 HTML 可直接跑
- [ ] `python3.8 main.py shop crawl --platform xxx --keyword "测试"` 真能出 JSON

满足以上 10 条,即可合并。

## 8. 常见踩坑

- **selector 用了伪类 `:has()`** — lxml 不支持,改走 BeautifulSoup 的 `select`。
- **价格在 `<script>` 里** — 优先 `re.search(r'pageData\s*=\s*(\{.+?\})\s*;', html)`;实在找不到用 Playwright(本 skill 未集成)。
- **CDN 图片协议** — `//img.xxx.com/...` 拼 `https:` 前缀再存 `image_url`,否则前端展示 broken。
- **价格单位** — 京东/淘宝/拼多多都有"分"陷阱(参见 SKILL.md Pitfalls #2/#4),务必在 `_normalize_price` 集中处理,不要散在 N 个地方。
- **Unicode 标准化** — 标题里可能有 `　`(全角空格),`strip()` 不会清掉,加 `re.sub(r'\s+', ' ', title)`。
