create another command. I want this command to be match-pdfs. This will query the all the Models and will try to match the appropriate pdf from the data/pdfs folder.

The matching will be done by name and by keyword. Some examples:

Card: 

```
        "PurifyingFlame": {
            "characteristics": [],
            "faction": "Guild",
            "files": {
                "defaultBack": "cards/Guild/Purifying-Flame-back.jpg",
                "versions": [
                    {
                        "displayName": "Purifying Flame",
                        "front": "cards/Guild/Purifying-Flame-Front-0.jpg"
                    }
                ]
            },
            "id": "PurifyingFlame",
            "keywords": [
                "Witch Hunter"
            ],
            "meta": {
                "noHire": true
            },
            "name": "Purifying Flame",
            "station": "Totem",
            "stats": {
                "cost": 0,
                "df": "6",
                "health": 9,
                "limit": 1,
                "sm": "0",
                "sp": "7",
                "sz": "2",
                "wp": "3"
            },
            "text": "Purifying Flame\t3\t6\t7\t2\t-\t9\tWitch Hunter\tTotem\tGuild",
            "tokens": []
        },

```

will match to: pdfs/M4E_Stat_Witch-Hunter_Purifying_Flame.pdf

This matches the name (Purifying Flame and Purifying_Flame)
This also matches the keyword (Witch_Hunter vs Witch Hunter)

in general, all cards in pdf have this structure:
M4E_Stat_(Keyword1)_(Keyword2)_(Name).pdf


Another example:

```
        "Ceddra_SightlessSnow": {
            "alternates": [
                "Ceddra_WhiteStag"
            ],
            "characteristics": [],
            "faction": "Arcanists",
            "files": {
                "defaultBack": "cards/Arcanists/Ceddra-Sightless-Snow-back.jpg",
                "versions": [
                    {
                        "displayName": "Ceddra, Sightless Snow",
                        "front": "cards/Arcanists/Ceddra-Sightless-Snow-front-0.jpg"
                    }
                ]
            },
            "id": "Ceddra_SightlessSnow",
            "keywords": [
                "December",
                "Chimera"
            ],
            "meta": {},
            "name": "Ceddra",
            "station": "Unique",
            "stats": {
                "cost": 7,
                "df": "5",
                "health": 9,
                "limit": 1,
                "sm": "0",
                "sp": "6",
                "sz": "2",
                "wp": "5"
            },
            "text": "Ceddra (Sightless Snow)\t5\t5\t6\t2\t7\t8\tDecember/Chimera\tUnique\tArcanists",
            "title": "Sightless Snow",
            "tokens": []
        },

```

Will match to pdfs/Arcanists/M4E_Stat_December_Ceddra_Sightless_Snow.pdf

another: 

```
        "GhostEater": {
            "characteristics": [],
            "faction": "Resurrectionist",
            "files": {
                "defaultBack": "cards/Resurrectionist/Ghost-Eater-back.jpg",
                "versions": [
                    {
                        "displayName": "Ghost Eater",
                        "front": "cards/Resurrectionist/Ghost-Eater-front-0.jpg"
                    }
                ]
            },
            "id": "GhostEater",
            "keywords": [
                "Ancestor",
                "Revenant"
            ],
            "meta": {},
            "name": "Ghost Eater",
            "station": "Unique",
            "stats": {

                "cost": 8,
                "df": "5",
                "health": 11,
                "limit": 1,
                "sm": "0",
                "sp": "6",
                "sz": "2",
                "wp": "5"
            },
            "text": "Ghost Eater\t5\t5\t6\t2\t8\t11\tAncestor/Revenant\tUnique\tResurrectionist",
            "tokens": []
        },

```

will match:

pdfs/Resurrectionists/M4E_Stat_Ancestor_Revenant_Ghost_Eater.pdf


In this case this matches two keywords: Ancestor and Revenant.

We need to create another field in Model, called pdf which will be the matched pdf. 
The command needs to loop all models and, for each, try to guess what is the correct pdf for that. 
For that, get model.faction and then, try and search it inside `pdfs/(Faction)/*.pdf`

Create a report only with those models that failed matching the pdf
