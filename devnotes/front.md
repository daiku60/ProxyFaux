let's focus now on the frontend. I want to use shadcn as the components library and react router (not remix) as the router.

Right now I only need one route to the main page. That page needs to have:

- a Text area where the user can paste the cards. Example:

Brew @ Informants (Bayou)
Leader:
  Brewmaster, Proof Prophet
Totem(s):
  Apprentice Wesley
Hires:
  Hopscotch
  Shojo
  Popcorn Turner
  Barrelby
  Squish and Squash
  Lucky Fate, Effigy
  Nia, Life of the Party
References:
  Whiskey Gamin
  Lucky Fate, Emissary

- a view where we'll see a preview of the front side of that model
- some options for exporting:
  - sheet size: Letter or A4
  - checkbox include border
  - checkbox include cut lines

- an export button that will make the request to `/api/create-pdf` with the options selected and the text on the text area.

Upon clicking the create button and receiving the file, it will open another tab with the contents of the pdf.
