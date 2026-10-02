---
title: 'Sample Document'
lang: en-US
---

Version 1.2, pages:

# Introduction {#introduction}

Plain text with *italic*, **bold**, `code_text()` and E = mc^2^. A footnote[^1] follows.

Characters that are markup elsewhere: \* \_ \` \[x\] \| \~ \^ # \{author} -\- \<\<a>> a::b -> 50 % & 100\$— a dash, a forced\
line break and café über, ½ × 3° and x³.

1\. Not a list, because it is a body paragraph.

Hidden text follows.

## Lists {#lists}

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

## Tables and graphics {#tables-and-graphics}

See [“Introduction” on page \pageref{introduction}](#introduction) and the table below.

+-------------------------+-------------------------+------------------------------------------------+
| Name                    | Value                   | Notes                                          |
+=========================+=========================+================================================+
| Spans two columns                                 | Spans two rows.                                |
+-------------------------+-------------------------+                                                |
| alpha                   | 42                      | Second paragraph \| with a bar.                |
+-------------------------+-------------------------+------------------------------------------------+

: Sample table

![](images/dot.png){width=50%}

Figure 1: A small picture.

A graphic stored in the file is left out.

## More structures {#more-structures}

### Lists with references {#lists-with-references}

1. Read [“Tables and graphics” on page \pageref{tables-and-graphics}](#tables-and-graphics) first.

2. Then check the parts in this table:

   +---------------------------------------------------------------------------------------------------+
   | Parts and notes                                                                                   |
   +------------------------------------+--------------------------------------------------------------+
   | Part                               | Notes                                                        |
   +====================================+==============================================================+
   | 1. Open the lid                    | Handle with care[^2].                                        |
   | 2. Close it again                  |                                                              |
   +------------------------------------+--------------------------------------------------------------+
   | ![](images/dot.png){width=19%}     | - light                                                      |
   |                                    | - small                                                      |
   +------------------------------------+--------------------------------------------------------------+
   | Total                              | 2 parts                                                      |
   +------------------------------------+--------------------------------------------------------------+

   : Parts

3. Finish with an inline ![](images/dot.png){width=4%} picture.

A paragraph between two parts of a list.

4. The list goes on with step four.

#### Formatting and quotes {#formatting-and-quotes}

Underlined [words]{.underline}, struck out ~~words~~, H~2~O, a tab and a hard space.

> A quoted paragraph.
>
> Its second paragraph, see [“Lists with references” on page \pageref{lists-with-references}](#lists-with-references).

Two graphics in one frame:

![](images/dot.png){width=50%}

![](images/dot.png){width=10%}

[^1]: The footnote text.

[^2]: A note from a table cell.
