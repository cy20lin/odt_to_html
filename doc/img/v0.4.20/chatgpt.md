You:

given sample.html, sample.odt/content.xml
(html 去除 base64 encoded image data)

figure 3 選項設定視窗 的位置不對 為什麼

ChatGPT:

這個案例其實**非常關鍵**，而且你現在遇到的不是 SVG 或 arrow 的問題，而是 **ODT「as-char anchor + y offset」語意被誤解** 的典型坑。

我直接結論先給，再拆解原因。

---

## 結論（先講為什麼 Figure 3 會跑掉）

**Figure 3 位置不對的根本原因是：**

> 你把  
> `text:anchor-type="as-char"`  
> **錯誤地當成 page / paragraph 絕對定位在處理**  
> 尤其是 `svg:y="-3.0583in"` 這個值。

在 ODT 中：

-   `as-char` **不是絕對座標**
    
-   `svg:y` 在 `as-char` 情況下 **不是 top**
    
-   而是 **baseline-relative vertical offset（baseline shift）**
    

但目前你的 HTML 輸出是：

```html
<div class="drawing-frame"
     style="position: absolute; top: -3.0583in">
```

👉 這一步語意已經錯了，所以整個 Figure 3 被「往頁面上方拉走」。

---

## 精確拆解：ODT 在這裡真正的語意是什麼

### 原始 ODT

```xml
<draw:frame
    text:anchor-type="as-char"
    svg:y="-3.0583in"
    svg:width="3.6472in">
```

### 在 LibreOffice Writer 中的意思是：

-   這個 frame **是 inline object**
    
-   它佔據一個「字元位置」
    
-   `svg:y="-3.0583in"` 表示：
    

> **相對於該行文字 baseline 向上移動 3.0583 吋**

不是：

-   ❌ 距離 paragraph top
    
-   ❌ 距離 page top
    
-   ❌ 絕對座標
    

---

## 你現在的 HTML 發生了什麼事

### HTML 結構（簡化）

```html
<p>
  <div class="drawing-frame"
       style="position: absolute; top: -3.0583in">
```

### 問題點有三個（很重要）

### ❌ 問題 1：as-char 不該用 `position:absolute`

`as-char` 在 ODT ≈ HTML 的：

-   `inline-block`
    
-   `vertical-align`
    
-   baseline-relative offset
    

而不是 absolute positioning。

---

### ❌ 問題 2：`svg:y` 被錯誤映射為 `top`

`svg:y` 在 `as-char` 情境下語意是：

```scss
baseline + y-offset
```

但你用了：

```css
top: y
```

→ 直接把 inline object 拉出 flow。

---

### ❌ 問題 3：放在 anchor-page-content 之後放大了錯誤

因為你現在有：

```html
anchor-page (relative)
└── anchor-page-content (relative)
    └── p
        └── drawing-frame (absolute; top:-3in)
```

所以這個錯誤的 `top:-3in`  
**真的就把 Figure 3 拉到頁面上方去了**  
（而在 LibreOffice 它其實只是「浮在該行上方」）

---

## 為什麼其他圖看起來是對的？

因為它們是：

```xml
text:anchor-type="paragraph"
svg:x="..."
svg:y="..."
```

這種在 ODT 中才是：

-   真正的「paragraph-relative absolute positioning」
    
-   你 Phase 1 + Phase 2 的 anchor 邏輯正確適用的對象
    

👉 **只有 `as-char` 是例外**

---

## 正確處理 as-char 的原則（非常重要）

### 核心規則（請記住）

> **as-char = inline object，不是 positioned object**

### 正確 mapping 應該是：

| ODT | HTML |
| --- | --- |
| `text:anchor-type="as-char"` | `display:inline-block` |
| `svg:y` | `vertical-align` 或 `transform: translateY()` |
| 不影響 paragraph flow | 不用 absolute |
| 佔一個字元位置 | inline |

---

## 實作層面的具體建議（Phase 2 不會破壞）

### 1️⃣ 明確分支處理

在 code 中：

```python
if anchor_type == "as-char":
    # ❌ 不要 position:absolute
    # ❌ 不要把 svg:y 當 top
```

### 2️⃣ 建議 HTML 表現（最安全）

```html
<span class="anchor-char drawing-frame"
      style="
        display: inline-block;
        transform: translateY(-3.0583in);
      ">
```

或較保守：

```html
style="vertical-align: -3.0583in"
```

（transform 比較穩定，vertical-align 各 browser 行為略不同）

---

## 為什麼 Figure 3 特別明顯「跑掉」

因為它：

-   anchor = `as-char`
    
-   y = **\-3 吋以上（很大）**
    
-   又被你當成 page-relative absolute positioning
    

\=> 錯誤被「放大到肉眼可見」

---

## 一句話總結

> **Figure 3 跑掉不是 page-anchor 的錯，而是 as-char 被誤當成 absolute-positioned element。**

你現在 Phase 2 的方向是對的，  
**但 as-char 是必須獨立於 anchor-page / anchor-paragraph 之外處理的特殊類型**。

---

如果你願意，下一步我可以幫你做三件事之一：

1.  🔧 幫你寫一段「as-char 專用 mapping 規則（pseudo code）」
    
2.  📐 幫你定義 `anchor-char` 的最小 CSS contract
    
3.  🧪 幫你設計一個「一眼就能驗證 as-char 正確性的 test case」
    

這一關你其實已經快破完了，只差把 **as-char 從 absolute 世界拉回 inline 世界