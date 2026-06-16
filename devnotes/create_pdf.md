let's do the api now. I want an endpoint that, given a text containing model names (separated by comma or line break) to store and return a single pdf that is the composition of the pdfs of those model's.pdf values, the following way:

- The resulting pdf needs to have the size of an A4 vertical sheet (210mm x 297mm). It can have multiple pages of that size.
- Inside each page, there'll be a grid of 2x2 cards of size 70mm x 120mm. Each space on the grid will have one of the pages of the model's pdf.
- Each model pdf has two pages: first page is the up side and the other is the down side. They need to be next to each other.
- If the model pdf has {A|B} format, then take into account if the model name ended with A or B. If that is the case, then use the correspoding case (If we get Abomination A, then replace `{A|B}` with `A`). Otherwise use them in alphabetic order.

Example text: 

```
(Arcanists)
Leader:
  Rasputina, Abominable
Totem(s):
  Mara
Hires:
  Kaltgeist
  Kaltgeist
  Kaltgeist
```

This should give the following layout:

### Page 1

| Rasputina, Abominable (1st page) | Rasputina, Abominable (2nd page) |
| Mara (1st page)   | Mara (2nd page) |

### Page 2

| Kaltgeist (A, 1st page) | Kaltgeist (A, 2nd page) |
| Kaltgeist (B, 1st page) | Kaltgeist (B, 2nd page) |

### Page 3
| Kaltgeist (C, 1st page) | Kaltgeist (C, 2nd page) |


