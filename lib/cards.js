'use strict';
const escapeHtml = text => String(text ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
function renderCard(lead) {
  const e = x => escapeHtml(String(x ?? '').slice(0, 500));
  const text = [
    lead.is_demo ? '🧪 <b>DEMO: вымышленный пример</b>' : '📋 <b>Лид — требуется проверка владельца</b>',
    `Компания: <b>${e(lead.company_name)}</b>`,
    `Город: ${e(lead.city)} · Ниша: ${e(lead.niche)}`,
    `Оценка: ${e(lead.score_0_100)}/100 · ${e(lead.classification)} · ${e(lead.scoring_method)}`,
    `Статус: ${e(lead.status)} · Сайт: ${e(lead.website_status)}`,
    `Основание: ${e(lead.proof_quote)}`,
    `Почему: ${e(lead.why_relevant)}`,
    `Оффер: ${e(lead.offer_type)}`,
    `Контакт: ${e(lead.public_contact || 'Не указан')}`,
    `Черновик (v${e(lead.draft_version || 1)}): ${e(lead.draft_message)}`,
    `ID: <code>${e(lead.lead_id || 'после сохранения')}</code>`,
    'КП не отправлено. Одобрение относится к ручной отправке.',
  ].join('\n');
  const rows = [];
  if (lead.lead_id) rows.push([
    { text: 'Одобрить', callback_data: `a:${lead.lead_id}:${lead.draft_version || 1}` },
    { text: 'Не беспокоить', callback_data: `r:${lead.lead_id}` },
  ], [{ text: 'Изменить черновик', callback_data: `d:${lead.lead_id}` }]);
  if (lead.source_url) rows.push([{ text: 'Открыть источник', url: lead.source_url }]);
  return { text, parse_mode: 'HTML', disable_web_page_preview: true, reply_markup: { inline_keyboard: rows } };
}
module.exports = { renderCard, escapeHtml };
