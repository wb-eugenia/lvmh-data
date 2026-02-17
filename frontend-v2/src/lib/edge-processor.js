/**
 * Edge Processor - PII + Cleaning + RGPD Keywords
 * Ported from Python (text_cleaner.py + rgpd_filter.py)
 * Runs entirely in the browser
 */

const PII_PATTERNS = {
  email: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/gi,
  phone_fr: /(?:\+33|0)[1-9](?:\s?-?\d{2}){4}/g,
  phone_es: /\+34\d{9}/g,
  phone_it: /\+39\d{9,10}/g,
  phone_de: /\+49\d{10,11}/g,
  phone_uk: /\+44\d{10,11}/g,
  iban: /\b[A-Z]{2}\d{2}\s?(?:[A-Z0-9]{4}\s?){1,7}[A-Z0-9]{0,4}\b/g,
  carte_bancaire: /(?<![A-Z])\b(?:\d{4}[\s-]?){2,3}[\dX]{4,6}\b|\b\d{15,16}\b/g,
  ssn_us: /\b\d{3}-\d{2}-\d{4}\b/g,
  numero_secu_fr: /\b[12]\s?\d{2}\s?\d{2}\s?(?:0\d|[1-9]\d)\s?\d{3}\s?\d{3}\s?(?:0\d|1[0-8])\b/g,
  carte_vitale: /\b1(?:\s?\d){12,15}\b/g,
  dni_es: /\b\d{8}[A-Z]\b/g,
  nif_es: /\b[XYZA-Z]\d{7,8}[A-Z]\b/g,
  codice_fiscale: /\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b/g,
  passport: /\b(?:passport|passeport|pasaporte)[\s:]?[A-Z]?\d{6,9}\b/gi,
  code_porte: /\b(?:code|gate|porta|codigo|Türcode|buzzer|interphone)\s*(?:porte|entry|acces|porta|puerta)?\s*:?\s*\d{3,6}\b/gi,
  client_vip: /\b(?:VIP|client)\s*#?\s*\d{4,8}\b/gi,
};

const FILLER_PATTERNS = {
  FR: [
    /\b(euh|hum|bah|ben|bon|hein|quoi|voilà|alors|donc)\b/gi,
    /\b(tu sais|vous savez|tu vois|vous voyez)\b/gi,
    /\b(en fait|du coup|en gros|grosso modo)\b/gi,
    /\b(disons|disons que|on va dire)\b/gi,
    /\b(en quelque sorte|en quelque manière|pour ainsi dire|en quelque façon)\b/gi,
    /\b(c'est-à-dire|à peu près)\b/gi,
    /\b(eh bien|enfin|bref|là|machin|chose|truc|style|genre)\b/gi,
    /\b(si tu veux|si vous voulez|je veux dire|bonjour|salut|hello)\b/gi,
  ],
  EN: [
    /\b(uh|um|er|ah|hmm|well|okay|ok|yeah|yep|right)\b/gi,
    /\b(you know|you see|I mean|I guess|I suppose)\b/gi,
    /\b(you know what I mean)\b/gi,
    /\b(sort of|kind of|like|basically|actually|literally)\b/gi,
    /\b(let me see|let's see)\b/gi,
  ],
  IT: [
    /\b(eh|ehm|beh|boh|va bene|ok|allora|quindi|cioè|insomma)\b/gi,
    /\b(tipo|tipo così|diciamo|praticamente|capito|sai|capisci)\b/gi,
  ],
  ES: [
    /\b(eh|em|pues|bueno|vale|ok|entonces|ya)\b/gi,
    /\b(ya sabes|ya ves|sabes)\b/gi,
    /\b(tipo|bueno|verás)\b/gi,
  ],
  DE: [
    /\b(ähm|hm|öhm|ja|nee|also|oder|weiß|also)\b/gi,
    /\b(weist du|weißt du|Sie wissen)\b/gi,
  ],
};

const RGPD_KEYWORDS = {
  health_mental: [
    'burnout', 'dépression', 'dépressive', 'anxiété', 'anxieux', 'anxiété pathologique',
    'stress chronique', 'épuisement', 'trouble bipolaire', 'schizophrénie',
    'TOC', 'trouble obsessionnel', 'attaques de panique', 'phobie',
    'trouble alimentaire', 'anorexie', 'boulimie', 'addiction', 'toxicomanie',
    'suicide', 'tentative de suicide', 'automutilation'
  ],
  health_physical: [
    'maladie chronique', 'diabète', 'cancer', 'tumeur', 'métastase',
    'hospitalisé', 'hospitalisation', 'opération', 'chirurgie', 'intervention',
    'handicap', 'handicapé', 'mobilité réduite', 'fauteuil roulant',
    'maladie grave', 'maladie terminale', 'sida', 'VIH', 'hépatite',
    'épilepsie', 'sclérose', 'parkinson', 'alzheimer', 'démence'
  ],
  family_conflict: [
    'divorce conflictuel', 'divorce difficile', 'contentieux divorce',
    'garde enfants', 'droit de garde', 'placement enfants',
    'procès', 'avocat', 'tribunal', 'juridique',
    'conflit familial', 'rupture familiale', 'dispute familiale'
  ],
  religion: [
    'religion', 'croyance', 'foi', 'musulman', 'juif', 'chrétien',
    'catholique', 'protestant', 'orthodoxe', 'bouddhiste', 'hindou',
    'prière', 'mosquée', 'synagogue', 'église', 'temple'
  ],
  political: [
    'opinion politique', 'vote', 'élection', 'parti politique',
    'gauche', 'droite', 'extrêmiste', 'manifestation',
    'mouvement politique', 'idéologie'
  ],
  sexual_orientation: [
    'orientation sexuelle', 'homosexuel', 'lesbienne', 'gay',
    'bisexuel', 'transgenre', 'trans', 'genre',
    'mariage homosexuel', 'PACS'
  ],
  ethnic_origin: [
    'origines', 'ethnie', 'racial', 'minorité',
    'immigration', 'migrant', 'réfugié'
  ]
};

const PII_MASKS = {
  email: '[EMAIL]',
  phone_fr: '[PHONE]',
  phone_es: '[PHONE]',
  phone_it: '[PHONE]',
  phone_de: '[PHONE]',
  phone_uk: '[PHONE]',
  iban: '[RIB]',
  carte_bancaire: '[CARTE]',
  ssn_us: '[SSN]',
  numero_secu_fr: '[SECU]',
  carte_vitale: '[CARTE_VITALE]',
  dni_es: '[DNI]',
  nif_es: '[NIF]',
  codice_fiscale: '[FISCAL]',
  passport: '[PASSPORT]',
  code_porte: '[CODE]',
  client_vip: '[VIP_ID]',
};

function anonymizePII(text) {
  let result = text;
  
  for (const [key, pattern] of Object.entries(PII_PATTERNS)) {
    const mask = PII_MASKS[key] || '[PII]';
    result = result.replace(pattern, mask);
  }
  
  return result;
}

function removeFillers(text, language = 'FR') {
  const patterns = FILLER_PATTERNS[language] || FILLER_PATTERNS.FR;
  let result = text;
  
  for (const pattern of patterns) {
    result = result.replace(pattern, '');
  }
  
  result = result.replace(/\s+/g, ' ');
  result = result.replace(/\s+([.,;:!?])/g, '$1');
  result = result.trim();
  
  return result;
}

function detectRGPDRisk(text) {
  const lowerText = text.toLowerCase();
  const detected = [];
  
  for (const [category, keywords] of Object.entries(RGPD_KEYWORDS)) {
    for (const keyword of keywords) {
      if (lowerText.includes(keyword.toLowerCase())) {
        detected.push(category);
        break;
      }
    }
  }
  
  return {
    detected: detected.length > 0,
    categories: [...new Set(detected)]
  };
}

function normalizeText(text) {
  let result = text;
  
  result = result.replace(/\s+/g, ' ');
  result = result.replace(/\s+([.,;:!?])/g, '$1');
  result = result.replace(/([.!?])\1+/g, '$1');
  result = result.trim();
  
  return result;
}

export function processTextEdge(text, language = 'FR') {
  const originalText = text;
  
  const rgpdRisk = detectRGPDRisk(originalText);
  
  let cleaned = anonymizePII(text);
  
  cleaned = removeFillers(cleaned, language);
  
  cleaned = normalizeText(cleaned);
  
  return {
    text: cleaned,
    text_preprocessed: true,
    rgpd_risk: rgpdRisk,
    original_length: originalText.length,
    cleaned_length: cleaned.length
  };
}

export function processTextEdgeWithOriginal(text, language = 'FR') {
  const result = processTextEdge(text, language);
  
  return {
    ...result,
    original: text
  };
}

export function analyzePIICounts(text) {
  const counts = {};
  
  for (const [key, pattern] of Object.entries(PII_PATTERNS)) {
    const matches = text.match(pattern);
    if (matches) {
      counts[key] = matches.length;
    }
  }
  
  return counts;
}

export {
  anonymizePII,
  removeFillers,
  detectRGPDRisk,
  normalizeText,
  PII_PATTERNS,
  FILLER_PATTERNS,
  RGPD_KEYWORDS
};

export default processTextEdge;
