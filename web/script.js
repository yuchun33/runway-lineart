'use strict';

const $ = (selector) => document.querySelector(selector);
const state = { brands: [], brand: 0, season: null, look: 0, mode: 'grid', page: 0, direction: 1 };
const gallery = $('#gallery');
const brand = () => state.brands[state.brand];
const seasonOf = (look) => look.season || '未分類';
const currentLooks = () => state.season === null
  ? brand().looks
  : brand().looks.filter((look) => seasonOf(look) === state.season);

function renderSeasons() {
  const seasons = [null, ...new Set(brand().looks.map(seasonOf))];
  if (!seasons.includes(state.season)) state.season = null;
  const tabs = $('#seasons');
  tabs.replaceChildren();
  gallery.removeAttribute('aria-labelledby');
  seasons.forEach((season, index) => {
    const tab = document.createElement('button');
    tab.type = 'button';
    tab.id = `season-${state.brand}-${index}`;
    tab.textContent = season === null ? '全部' : season;
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-controls', 'gallery');
    const selected = season === state.season;
    tab.setAttribute('aria-selected', selected);
    tab.tabIndex = selected ? 0 : -1;
    if (selected) gallery.setAttribute('aria-labelledby', tab.id);
    tab.addEventListener('click', () => {
      if (state.season === season) return;
      state.season = season;
      state.look = 0;
      state.page = 0;
      [...tabs.children].forEach((button) => {
        const active = button === tab;
        button.setAttribute('aria-selected', active);
        button.tabIndex = active ? 0 : -1;
      });
      gallery.setAttribute('aria-labelledby', tab.id);
      render();
    });
    tab.addEventListener('keydown', (event) => {
      let target;
      if (event.key === 'ArrowRight') target = (index + 1) % seasons.length;
      if (event.key === 'ArrowLeft') target = (index - 1 + seasons.length) % seasons.length;
      if (event.key === 'Home') target = 0;
      if (event.key === 'End') target = seasons.length - 1;
      if (target === undefined) return;
      event.preventDefault();
      tabs.children[target].focus();
      tabs.children[target].click();
    });
    tabs.append(tab);
  });
}
const images = (look) => [
  { ...look.original, name: '原始圖片' },
  ...look.linearts.map((item, index) => ({ ...item, name: item.name || `線稿版本 ${index + 1}` }))
];

function imageElement(item, lazy = true) {
  const img = document.createElement('img');
  img.alt = item.alt || item.name;
  img.loading = lazy ? 'lazy' : 'eager';
  img.addEventListener('error', () => {
    img.parentElement.classList.add('failed');
    img.parentElement.disabled = true;
  }, { once: true });
  img.src = item.src;
  return img;
}

function card(item, look, lookIndex) {
  const figure = document.createElement('figure');
  figure.dataset.look = lookIndex;
  figure.classList.toggle('selected', state.look === lookIndex);
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'image-button';
  button.setAttribute('aria-label', `放大 ${look.name} · ${item.name}`);
  button.append(imageElement(item));
  button.addEventListener('click', () => {
    state.look = lookIndex;
    updateControls();
    gallery.querySelectorAll('figure').forEach((node) => node.classList.toggle('selected', Number(node.dataset.look) === lookIndex));
    $('#preview-image').src = item.src;
    $('#preview-image').alt = item.alt || item.name;
    $('#preview-caption').textContent = `${brand().name} / ${look.name} / ${item.name}`;
    $('#lightbox').showModal();
  });
  const caption = document.createElement('figcaption');
  caption.textContent = `${look.name} / ${item.name}`;
  figure.append(button, caption);
  return figure;
}

function updateControls() {
  const count = currentLooks().length;
  $('#collection-name').textContent = brand().name;
  $('#position').textContent = count ? `${String(state.look + 1).padStart(2, '0')} / ${String(count).padStart(2, '0')}` : '00 / 00';
  $('#previous').disabled = state.look <= 0;
  $('#next').disabled = state.look >= count - 1;
  document.querySelectorAll('[data-mode]').forEach((button) => button.setAttribute('aria-pressed', button.dataset.mode === state.mode));
  [...$('#brands').children].forEach((button, index) => button.setAttribute('aria-pressed', index === state.brand));
}

// Keep the thumbnail rail mounted while hovering so targets never jump away.
function arcRail() {
  const rail = document.createElement('nav');
  rail.className = 'arc-rail';
  rail.setAttribute('aria-label', '??????');
  const track = document.createElement('div');
  track.className = 'arc-track';
  const looks = currentLooks();
  track.style.height = `${Math.max(360, looks.length * 88 + 32)}px`;
  looks.forEach((look, index) => {
    const ratio = looks.length === 1 ? 0.5 : index / (looks.length - 1);
    const angle = (ratio - 0.5) * Math.PI * 0.8;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'arc-thumbnail';
    button.dataset.index = index;
    button.style.left = `${12 + Math.cos(angle) * 42}px`;
    button.style.top = `${16 + ratio * (Math.max(360, looks.length * 88 + 32) - 112)}px`;
    button.title = look.name;
    button.setAttribute('aria-label', `?? ${look.name} ??????`);
    button.setAttribute('aria-pressed', index === state.look);
    button.append(imageElement(look.original));
    const activate = () => {
      if (state.look === index) return;
      state.direction = index > state.look ? 1 : -1;
      state.look = index;
      state.page = 0;
      updateControls();
      updateCarousel();
    };
    button.addEventListener('pointerenter', (event) => {
      if (event.pointerType !== 'touch') activate();
    });
    button.addEventListener('focus', activate);
    button.addEventListener('click', activate);
    track.append(button);
  });
  rail.append(track);
  return rail;
}

function render() {
  updateControls();
  gallery.replaceChildren();
  gallery.className = state.mode === 'carousel' ? 'carousel' : `grid ${state.mode}`;
  $('#status').textContent = currentLooks().length ? '' : '此品牌尚未加入作品。';
  if (!currentLooks().length) return;
  if (state.mode !== 'carousel') {
    currentLooks().forEach((look, index) => {
      let items = images(look);
      if (state.mode === 'lineart') items = items.slice(1);
      if (state.mode === 'original') items = items.slice(0, 1);
      items.forEach((item) => gallery.append(card(item, look, index)));
    });
    if (!gallery.children.length) $('#status').textContent = '此季度尚未加入線稿。';
    return;
  }
  const carousel = document.createElement('div');
  carousel.className = 'arc-carousel';
  const panel = document.createElement('div');
  panel.className = 'carousel-panel';
  carousel.append(arcRail(), panel);
  gallery.append(carousel);
  updateCarousel();
}

function updateCarousel() {
  const panel = gallery.querySelector('.carousel-panel');
  panel.replaceChildren();
  gallery.querySelectorAll('.arc-thumbnail').forEach((button) => {
    button.setAttribute('aria-pressed', Number(button.dataset.index) === state.look);
  });
  const look = currentLooks()[state.look];
  const items = images(look);
  const pages = Math.ceil(items.length / 4);
  state.page = Math.min(state.page, pages - 1);
  const visible = items.slice(state.page * 4, state.page * 4 + 4);
  const stage = document.createElement('div');
  stage.className = `look-stage${state.direction < 0 ? ' backward' : ''}`;
  stage.style.setProperty('--columns', visible.length);
  visible.forEach((item) => stage.append(card(item, look, state.look)));
  panel.append(stage);
  if (pages > 1) {
    const controls = document.createElement('div');
    controls.className = 'version-controls';
    const label = document.createElement('span');
    label.textContent = `圖片 ${state.page * 4 + 1}–${Math.min((state.page + 1) * 4, items.length)} / ${items.length}`;
    for (const [delta, text] of [[-1, '← 前四張'], [1, '後四張 →']]) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = text;
      button.disabled = state.page + delta < 0 || state.page + delta >= pages;
      button.addEventListener('click', () => { state.page += delta; updateCarousel(); });
      controls.append(button);
    }
    controls.prepend(label);
    panel.append(controls);
  }

}

function selectLook(index) {
  if (index < 0 || index >= currentLooks().length) return;
  state.direction = index >= state.look ? 1 : -1;
  state.look = index;
  state.page = 0;
  if (state.mode === 'carousel') {
    updateControls();
    updateCarousel();
    gallery.querySelector(`.arc-thumbnail[data-index="${index}"]`)?.scrollIntoView({ block: 'nearest' });
  } else render();
  if (state.mode !== 'carousel') gallery.querySelector(`[data-look="${index}"]`)?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'center' });
}

$('#previous').addEventListener('click', () => selectLook(state.look - 1));
$('#next').addEventListener('click', () => selectLook(state.look + 1));
document.querySelectorAll('[data-mode]').forEach((button) => button.addEventListener('click', () => {
  state.mode = button.dataset.mode;
  render();
  if (state.mode !== 'carousel') gallery.querySelector(`[data-look="${state.look}"]`)?.scrollIntoView({ block: 'center' });
}));
$('#close-preview').addEventListener('click', () => $('#lightbox').close());
$('#lightbox').addEventListener('click', (event) => {
  if (event.target !== $('#lightbox')) return;
  const rect = $('#lightbox').getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) $('#lightbox').close();
});

async function init() {
  try {
    const response = await fetch('data.json');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.brands) || !data.brands.length) throw new Error('缺少品牌資料');
    state.brands = data.brands;
    state.brands.forEach((item, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = item.name;
      button.addEventListener('click', () => {
        state.brand = index;
        state.season = null;
        state.look = 0;
        state.page = 0;
        renderSeasons();
        render();
      });
      $('#brands').append(button);
    });
    renderSeasons();
    render();
  } catch (error) {
    $('#status').textContent = '無法載入作品資料。請使用本地 HTTP 伺服器開啟，並確認 data.json 格式正確。';
    $('#previous').disabled = $('#next').disabled = true;
    document.querySelectorAll('[data-mode]').forEach((button) => { button.disabled = true; });
    console.error(error);
  }
}
init();
