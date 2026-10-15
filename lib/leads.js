'use strict';
const { createHash } = require('crypto');
const { URL } = require('url');
const hash = text => createHash('sha256').update(text).digest('hex');
const SOCIAL = new Set(['vk.com', 't.me', 'instagram.com', 'threads.net', 'threads.com', 'facebook.com']);
const socialRoot = host => [...SOCIAL].find(root=>host===root||host.endsWith('.'+root));

function clean(value, max = 500, required = false) {
  if (value === undefined || value === null) value = '';
  if (typeof value !== 'string' || value.length > max) throw new Error('Неверный тип или длина поля');
  value = value.normalize('NFKC').trim();
  if (required && !value) throw new Error('Обязательное поле отсутствует');
  return value;
}

function canonicalUrl(value) {
  if (!value) return null;
  const url = new URL(clean(value, 2000));
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Нужен HTTP(S) URL без credentials');
  url.hostname = url.hostname.toLowerCase().replace(/^www\./, '');
  url.hash = '';
  for (const key of [...url.searchParams.keys()]) {
    if (/^(utm_|fbclid$|gclid$)/i.test(key)) url.searchParams.delete(key);
  }
  url.searchParams.sort();
  return url.toString().replace(/\/$/, '');
}

function normalizeLead(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('Лид должен быть объектом');
  if (raw.is_demo !== undefined && typeof raw.is_demo !== 'boolean') throw new Error('is_demo должен быть boolean');
  const company = clean(raw.company_name, 200, true);
  const city = clean(raw.city, 100);
  const text = clean(raw.text ?? raw.proof_quote, 20000, true);
  const source = clean(raw.source, 100, true);
  const sourceType = clean(raw.source_type || 'manual', 50);
  const sourceUrl = canonicalUrl(clean(raw.source_url, 2000, true));
  const website = canonicalUrl(raw.website);
  const niche = clean(raw.niche, 100);
  const externalId = clean(raw.external_id, 200);
  let identity,identityReview=false;
  const sourceParsed=new URL(sourceUrl);
  const sourceIsPost=(socialRoot(sourceParsed.hostname)==='t.me'&&/^\/[^/]+\/\d+$/.test(sourceParsed.pathname))||
    /\/(request|post)\/[^/]+/.test(sourceParsed.pathname)||/\/wall-?\d+_\d+/.test(sourceParsed.pathname);
  if (externalId) identity = 'external:' + source + ':' + externalId;
  else if(sourceIsPost) identity='post:'+sourceUrl;
  else if(website) {
    const parsed=new URL(website),social=socialRoot(parsed.hostname);
    if(social) { parsed.hostname=social;identity='profile:'+parsed.toString(); }
    else identity='domain:'+parsed.hostname;
  } else {
    identity='company:'+JSON.stringify([source,company.toLowerCase().replace(/\s+/g,' '),city.toLowerCase()]);
    identityReview=true;
  }
  let contact = clean(raw.public_contact, 300);
  const digits = contact.replace(/\D/g, '');
  if (/^[+\d\s().-]+$/.test(contact) && digits.length === 11 && /^[78]/.test(digits)) contact = '+7' + digits.slice(1);
  const published = raw.published_at ? new Date(raw.published_at) : null;
  if (published && Number.isNaN(published.getTime())) throw new Error('Неверная дата источника');
  const evidence = raw.website_evidence && typeof raw.website_evidence === 'object' ? raw.website_evidence : null;
  const verifiedAbsence = !website && raw.website_status === 'ABSENT_CONFIRMED' && evidence?.method === 'manual' &&
    evidence?.checked_at && Number.isFinite(Date.parse(evidence.checked_at)) && canonicalUrl(evidence?.source_url);
  const contactSource=contact ? canonicalUrl(raw.contact_source_url || sourceUrl) : null;
  return {
    source, source_type: sourceType, source_url: sourceUrl, company_name: company, niche, city,
    website, website_status: verifiedAbsence ? 'ABSENT_CONFIRMED' : website ? 'UNVERIFIED' : 'UNKNOWN',
    public_contact: contact || null,
    contact_source_url: contactSource,
    proof_quote: text, text, published_at: published?.toISOString() || null,
    is_demo: raw.is_demo === true, dedupe_key: hash((raw.is_demo===true?'demo:':'real:')+identity),identity_review:identityReview,
    content_hash: hash(JSON.stringify([company, city, niche, text, website, verifiedAbsence ? evidence : null,
      published?.toISOString()||null,contact,contactSource,sourceUrl])),
    attribution: { ...(raw.attribution && typeof raw.attribution==='object' && !Array.isArray(raw.attribution) ? raw.attribution : {}), source_url: sourceUrl, published_at: published?.toISOString() || null },
    tags: raw.is_demo === true ? ['DEMO'] : [],
  };
}

function chooseOffer(niche) {
  if (/директ|таргет|маркетинг|авито|продвижени|рекламн.{0,15}(кабинет|кампан)/i.test(niche)) return 'Маркетинг: Директ, VK, Авито и продвижение на картах';
  if (/crm|срм/i.test(niche)) return 'Внедрение CRM и автоматизация процессов';
  if (/звонк|лидогенерац/i.test(niche)) return 'Лидогенерация на звонках под согласованный сценарий';
  if (/отдел.{0,10}продаж|обучени.{0,10}продаж/i.test(niche)) return 'Построение отдела продаж и обучение продажам';
  if (/ии|фильм|мультфильм|ролик|фото|коммерческ.{0,10}видео/i.test(niche)) return 'ИИ-контент: фильмы, мультфильмы, реклама, фото и видео';
  if (/мебел|кухн/i.test(niche)) return 'Каталог мебели с заявками';
  if (/ресторан|доставк|кафе/i.test(niche)) return 'Онлайн-меню и оформление заказов';
  if (/отел|гостиниц/i.test(niche)) return 'Каталог номеров и заявки на бронь';
  if (/стомат|салон/i.test(niche)) return 'Услуги и онлайн-запись';
  if (/ремонт/i.test(niche)) return 'Калькулятор и приём заявок';
  if (/бот|автоматизац/i.test(niche)) return 'Telegram-бот и автоматизация заявок';
  return 'Сайт или автоматизация под подтверждённую задачу';
}

function scoreLead(lead, { now = new Date().toISOString() } = {}) {
  const t = lead.text.toLowerCase();
  let classification = 'IRRELEVANT', score = 20, confidence = 0.45;
  let why = 'Подтверждённого запроса нет; нужна ручная проверка.';
  const age = lead.published_at ? Date.parse(now) - Date.parse(lead.published_at) : Infinity;
  if (lead.source==='telegram_inbound' && lead.source_type==='website_forms' && lead.attribution?.intake==='telegram_inbound' && lead.attribution?.consent===true) {
    classification='DIRECT_REQUEST';score=95;confidence=0.9;
    why='Посетитель сам отправил задачу и контакт после явного согласия в боте.';
  } else if (/казино|без вложений|гарантированн.{0,10}доход|в штат|полная занятость/.test(t)) {
    why = 'Спам или вакансия в штат; не подтверждён запрос на подряд.';
    score = 5; confidence = 0.9;
  } else if (/делаю сайты|создаю сайты|разрабатываю сайты|заказывайте у меня|предлагаю.{0,25}(разработк|сайт|бот)/.test(t)) {
    classification = 'COMPETITOR'; score = 10; confidence = 0.9;
    why = 'Текст предлагает услуги исполнителя, а не ищет подрядчика.';
  } else if (/(нуж[её]н|нужна|нужно|ищ[уе]м|ищу|кто сделает).{0,60}(сайт|лендинг|магазин|разработчик|бот|автоматизац|видео|директ|таргет|маркетинг|авито|crm|срм|лидогенерац|звонк|отдел.{0,10}продаж|обучени.{0,10}продаж|ии|фильм|мультфильм|ролик|фото)/.test(t)) {
    classification = 'DIRECT_REQUEST'; score = age >= 0 && age <= 7 * 86400000 ? 95 : 80; confidence = 0.88;
    why = score >= 90 ? 'Прямой свежий запрос в тексте источника.' : 'Прямой запрос; свежесть нужно проверить.';
  } else if (/ищ[уе]м.{0,30}партн[её]р|субподряд|реферальн/.test(t)) {
    classification = 'PARTNER'; score = 65; confidence = 0.7; why = 'Есть сигнал о партнёрстве или субподряде.';
  } else if (lead.website_status === 'ABSENT_CONFIRMED') {
    classification = 'LIKELY_NEED'; score = 72; confidence = 0.6;
    why = 'Приложено подтверждение ручной проверки сайта; потребность ещё не подтверждена клиентом.';
  }
  const offer = chooseOffer(lead.niche + " " + lead.text);
  const draft = `Здравствуйте! В вашем сообщении: «${lead.proof_quote.slice(0,300)}». Могу обсудить решение: ${offer.toLowerCase()}. Подскажите, задача ещё актуальна?`;
  return { ...lead, classification, score_0_100: score, confidence_0_1: confidence,
    why_relevant: why, need_detected: classification === 'DIRECT_REQUEST' ? lead.proof_quote.slice(0,500) : '',
    offer_type: offer, draft_message: draft, scoring_method: 'heuristic',
    score_0_100:lead.identity_review?Math.min(score,69):score,
    status: score < 40 || lead.identity_review ? 'REVIEW' : 'NEW', next_action: 'Проверить источник и актуальность', estimated_cost: 0 };
}

module.exports = { normalizeLead, scoreLead, canonicalUrl, chooseOffer };
