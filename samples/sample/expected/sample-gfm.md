# Sample Document

Version 1.2, pages:

<a id="introduction"></a>
## Introduction

Plain text with *italic*, **bold**, `code_text()` and E = mc<sup>2</sup>. A footnote[^1] follows.

Characters that are markup elsewhere: \* \_ \` \[x\] \| \~ \^ # {author} -- \<\<a>> a::b -> 50 % & 100\$— a dash, a forced\
line break and café über, ½ × 3° and x³.

1\. Not a list, because it is a body paragraph.

Hidden text follows.

### Lists

- First bullet

  - Nested bullet

- Second bullet

  A paragraph that continues the second bullet.

<!-- -->

1. Step one
2. Step two

<!-- -->

1. A new list, step one again

```
for x in range(3):
    print(x * 2)
```

<a id="tables-and-graphics"></a>
### Tables and graphics

See [“Introduction” on page 2](#introduction) and the table below.

**Table 1: Sample table**

<table>
<tr><th>Name</th><th>Value</th><th>Notes</th></tr>
<tr><td colspan="2">Spans two columns</td><td rowspan="2"><p>Spans two rows.</p><p>Second paragraph | with a bar.</p></td></tr>
<tr><td>alpha</td><td>42</td></tr>
</table>

![](images/dot.png)

Figure 1: A small picture.

A graphic stored in the file is left out.

### More structures

<a id="lists-with-references"></a>
#### Lists with references

1. Read [“Tables and graphics” on page 3](#tables-and-graphics) first.

2. Then check the parts in this table:

   <table>
   <tr><th colspan="2">Parts and notes</th></tr>
   <tr><th>Part</th><th>Notes</th></tr>
   <tr><td><ol><li>Open the lid</li><li>Close it again</li></ol></td><td>Handle with care (A note from a table cell.).</td></tr>
   <tr><td><img src="images/dot.png" alt=""></td><td><ul><li>light</li><li>small</li></ul></td></tr>
   <tr><td>Total</td><td>2 parts</td></tr>
   </table>

   **Table 2: Parts**

3. Finish with an inline ![](images/dot.png) picture.

A paragraph between two parts of a list.

4. The list goes on with step four.

##### Formatting and quotes

Underlined <ins>words</ins>, struck out ~~words~~, H<sub>2</sub>O, a tab and a hard space.

> A quoted paragraph.
>
> Its second paragraph, see [“Lists with references” on page 3](#lists-with-references).

Two graphics in one frame:

![](images/dot.png)

![](images/dot.png)

[^1]: The footnote text.
