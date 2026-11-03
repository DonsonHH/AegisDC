(() => {
  'use strict';
  const filter = document.querySelector('#parameter-filter');
  const status = document.querySelector('#filter-status');
  const rows = [...document.querySelectorAll('.parameters tbody tr')];
  filter.addEventListener('change', () => {
    let visible = 0;
    for (const row of rows) {
      row.hidden = filter.value === 'gaps' && row.dataset.availability === 'documented';
      if (!row.hidden) visible++;
    }
    status.textContent = `当前显示${visible}条 / 共${rows.length}条记录`;
  });
  const dialog = document.querySelector('#figure-dialog');
  const canvas = document.querySelector('#figure-canvas');
  const scale = document.querySelector('#figure-scale');
  let opener;
  function setScale() {
    const svg = canvas.querySelector('svg');
    if (svg) svg.style.width = `${1240 * Number(scale.value) / 100}px`;
  }
  for (const button of document.querySelectorAll('.zoom')) {
    button.addEventListener('click', () => {
      opener = button;
      const figure = document.querySelector(`#fig-${button.dataset.figure}`);
      const svg = figure.querySelector('svg').cloneNode(true);
      // Namespace copied IDs and references to keep the document's IDs unique.
      const prefix = `dialog-${button.dataset.figure}-`;
      const idMap = new Map([...svg.querySelectorAll('[id]')].map(e => [e.id, prefix + e.id]));
      for (const element of [svg, ...svg.querySelectorAll('*')]) {
        for (const attribute of [...element.attributes]) {
          let value = attribute.value;
          if (attribute.name === 'id') value = idMap.get(value) || value;
          if (attribute.name === 'aria-labelledby') value = value.split(' ').map(id => idMap.get(id) || id).join(' ');
          for (const [id, replacement] of idMap) value = value.replaceAll(`url(#${id})`, `url(#${replacement})`);
          element.setAttribute(attribute.name, value);
        }
      }
      canvas.replaceChildren(svg);
      document.querySelector('#dialog-title').textContent = figure.querySelector('title').textContent;
      scale.value = '100';
      setScale();
      dialog.showModal();
      canvas.scrollTo(0, 0);
    });
  }
  scale.addEventListener('input', setScale);
  document.querySelector('#close-dialog').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => { canvas.replaceChildren(); if (opener) opener.focus(); });
})();
