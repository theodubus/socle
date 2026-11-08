<!-- socle: couche=demandes zone=publique -->
# {id} — {titre}

> date : {date}

## Décision demandée

Répondre librement aux questions de cadrage ci-dessous : la spécification
de ce sujet dépend d'une intention que la mémoire ne dit pas.

## Contexte

**Le projet.** <Ce que fait le projet, et pour qui, en une ou deux phrases, même si l'humain le sait.>

**Le chantier.** <Le but du travail en cours et pourquoi il existe, ce qui est fait et ce qui reste ; les décisions passées de l'humain qui y mènent, dites par leur contenu et leur date, pas par leur numéro.>

**La question.** <Le sujet à spécifier, ce que la mémoire en dit déjà, et ce qui manque pour le spécifier sans deviner.>

## Questions

1. **<Une question ouverte.>** Hypothèse de l'agent : <ce qu'il supposerait, ou « aucune »>.

## Éléments cités

<Chaque élément cité, décrit en clair sur place : jamais un identifiant seul.>

## Où regarder

<Un lien vers le sujet du backlog, et vers ce que la mémoire en dit.>

Ce qu'il faut vérifier : que chaque question demande ton intention, et
non un choix que l'agent pourrait trancher seul.

## Options

- **Répondre** : quelques minutes, ton texte en un ou plusieurs messages,
  que l'agent consigne tel quel ; risque faible, la spécification suit ce
  que tu veux ; réversible.
- **Valider les hypothèses** : effort nul ; risque, une hypothèse qui ne dit
  pas ton intention, notée « supposée », se corrige plus tard ; réversible.
- **Refuser** : effort nul ; risque, le sujet attend, sans spécification ;
  réversible.

## Conséquences

Si tu réponds, l'agent consigne ton texte exact, puis écrit la
spécification ou la décision qui en découle, et te la soumet dans une
demande. Si tu valides les hypothèses, il les applique, notées
« supposées ». Si tu refuses, le sujet attend. Si les questions ne se
comprennent pas (`contexte-insuffisant`), l'agent les réécrit. Sans
réponse, le sujet attend aussi, et l'agent travaille sur autre chose.

## Recommandation

<Valider les hypothèses si elles disent ton intention ; sinon répondre, même brièvement. Vérifié : ce que la mémoire établit. Supposé : le reste.>

## Réponses possibles

- `valider` — les hypothèses de l'agent s'appliquent, notées « supposées ».
- `reponses` — le texte de ta réponse, en un ou plusieurs messages, donne les réponses ; l'agent le consigne tel quel.
- `refuser` — le sujet attend, sans spécification.
- `contexte-insuffisant` — la demande revient à l'agent, qui la réécrit en une demande qui la remplace.
