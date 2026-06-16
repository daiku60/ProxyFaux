create a scrapper command in django that:

- takes backend/data/cards.json
- for each image found, download that image.
- create subdirectories for the relative path of this image
- for example, if the image is "cards/Neverborn/Crew-Marcus-Alpha-front.jpg", create cards/Neverborn inside data and store the image there named `Crew-Marcus-Alpha-front.jpg`
- the full url of the image has `https://firebasestorage.googleapis.com/v0/b/playwyrd.firebasestorage.app/o/` prepended and `?alt=media&token=a8b4396c-13f1-4aba-b1b8-3f24fdb5247d` appended. for example, the above image url would be `https://firebasestorage.googleapis.com/v0/b/playwyrd.firebasestorage.app/o/cards%2FNeverborn%2FCrew-Marcus-Alpha-front.jpg?alt=media&token=a8b4396c-13f1-4aba-b1b8-3f24fdb5247d`



https://firebasestorage.googleapis.com/v0/b/playwyrd.firebasestorage.app/o/cards%2FArcanists%2FArcane-Fate-Effigy-front-0.jpg?alt=media&token=fab0c55d-6fcc-46ed-9c93-d7c6857df6c1

https://firebasestorage.googleapis.com/v0/b/playwyrd.firebasestorage.app/o/cards%2FArcanists%2FArcane-Effigy-back.jpg?alt=media&token=fab0c55d-6fcc-46ed-9c93-d7c6857df6c1

https://firebasestorage.googleapis.com/v0/b/playwyrd.firebasestorage.app/o/cards%2FArcanists%2FArcane-Effigy-back.jpg?alt=media&token=04514cfc-0f54-4484-ab57-91d10a515312

https://firebasestorage.googleapis.com/v0/b/playwyrd.firebasestorage.app/o/cards%2FArcanists%2FArcane-Fate-Effigy-back.jpg?alt=media&token=04514cfc-0f54-4484-ab57-91d10a515312

