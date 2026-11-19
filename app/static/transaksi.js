(() => {
  const form = document.getElementById('sale-form');
  const input = document.getElementById('product-search');
  const selectedId = document.getElementById('selected-product-id');
  const listbox = document.getElementById('product-suggestions');
  const status = document.getElementById('product-search-status');
  const details = document.getElementById('selected-product-details');
  const quantityInput = document.getElementById('product-quantity');
  const addButton = document.getElementById('add-to-cart');
  const cartLines = document.getElementById('cart-lines');
  const cartPayload = document.getElementById('cart-payload');
  const csrfToken = form?.querySelector('input[name="csrf_token"]')?.value || '';
  if (!form || !input || !selectedId || !listbox || !status || !details
      || !quantityInput || !addButton || !cartLines || !cartPayload) return;

  let matches = [];
  const cart = new Map();
  let activeIndex = -1;
  let requestNumber = 0;
  let debounceTimer;

  const closeList = () => {
    listbox.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    activeIndex = -1;
  };

  const selectItem = (item) => {
    if (item.stok < 1) return;
    selectedId.value = String(item.id);
    input.value = item.nama_barang;
    input.setCustomValidity('');
    status.textContent = 'Barang berhasil dipilih.';
    details.textContent = `${item.nama_barang} · stok ${item.stok} unit · harga Rp ${Number(item.harga).toLocaleString('id-ID')}`;
    details.hidden = false;
    closeList();
  };

  const setActive = (nextIndex) => {
    const buttons = [...listbox.querySelectorAll('.product-suggestion:not(:disabled)')];
    if (!buttons.length) return;
    activeIndex = (nextIndex + buttons.length) % buttons.length;
    buttons.forEach((button, index) => {
      const isActive = index === activeIndex;
      button.classList.toggle('active', isActive);
      button.setAttribute('aria-selected', String(isActive));
    });
    input.setAttribute('aria-activedescendant', buttons[activeIndex].id);
  };

  const showMatches = (items) => {
    matches = items;
    listbox.replaceChildren();
    activeIndex = -1;
    for (const [index, item] of items.entries()) {
      const option = document.createElement('button');
      option.type = 'button';
      option.id = `product-suggestion-${index}`;
      option.className = 'product-suggestion';
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', 'false');
      option.disabled = item.stok < 1;

      const name = document.createElement('b');
      name.textContent = item.nama_barang;
      const info = document.createElement('small');
      info.textContent = item.stok > 0
        ? `Stok ${item.stok} · Rp ${Number(item.harga).toLocaleString('id-ID')}`
        : 'Stok habis';
      option.append(name, info);
      option.addEventListener('mousedown', (event) => event.preventDefault());
      option.addEventListener('click', () => selectItem(item));
      listbox.append(option);
    }
    listbox.hidden = items.length === 0;
    input.setAttribute('aria-expanded', String(items.length > 0));
    status.textContent = items.length
      ? `${items.length} saran ditemukan. Pilih barang yang sesuai.`
      : 'Tidak ada barang yang cocok.';
  };

  const search = async (query, currentRequest) => {
    try {
      const url = new URL(input.dataset.suggestionsUrl, window.location.origin);
      url.searchParams.set('q', query);
      const response = await fetch(url, { headers: { Accept: 'application/json' } });
      if (currentRequest !== requestNumber) return;
      if (!response.ok) throw new Error('suggestion request failed');
      const payload = await response.json();
      showMatches(payload.items || []);
    } catch {
      if (currentRequest !== requestNumber) return;
      closeList();
      status.textContent = 'Saran barang gagal dimuat. Coba ketik kembali.';
    }
  };

  input.addEventListener('input', () => {
    selectedId.value = '';
    input.setCustomValidity('');
    details.hidden = true;
    const query = input.value.trim();
    const currentRequest = ++requestNumber;
    clearTimeout(debounceTimer);
    if (!query) {
      matches = [];
      closeList();
      status.textContent = 'Mulai ketik untuk mencari barang.';
      return;
    }
    status.textContent = 'Mencari barang…';
    debounceTimer = setTimeout(() => search(query, currentRequest), 180);
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown' && !listbox.hidden) {
      event.preventDefault();
      setActive(activeIndex + 1);
    } else if (event.key === 'ArrowUp' && !listbox.hidden) {
      event.preventDefault();
      setActive(activeIndex < 0 ? 0 : activeIndex - 1);
    } else if (event.key === 'Enter' && !listbox.hidden) {
      event.preventDefault();
      const enabled = matches.filter((item) => item.stok > 0);
      if (enabled.length) selectItem(enabled[activeIndex < 0 ? 0 : activeIndex]);
    } else if (event.key === 'Escape') {
      closeList();
    }
  });

  input.addEventListener('focus', () => {
    if (input.value.trim() && !selectedId.value) {
      const currentRequest = ++requestNumber;
      search(input.value.trim(), currentRequest);
    }
  });

  const renderCart = () => {
    cartLines.replaceChildren();
    for (const [itemId, line] of cart) {
      const row = document.createElement('tr');
      const name = document.createElement('td');
      const quantity = document.createElement('td');
      const action = document.createElement('td');
      const remove = document.createElement('button');
      name.textContent = line.nama_barang;
      quantity.textContent = `${line.jumlah_terjual} unit`;
      remove.type = 'button';
      remove.className = 'button';
      remove.textContent = 'Hapus';
      remove.addEventListener('click', () => {
        cart.delete(itemId);
        renderCart();
      });
      action.append(remove);
      row.append(name, quantity, action);
      cartLines.append(row);
    }
    if (!cart.size) {
      const row = document.createElement('tr');
      const empty = document.createElement('td');
      empty.colSpan = 3;
      empty.textContent = 'Keranjang masih kosong.';
      row.append(empty);
      cartLines.append(row);
    }
    cartPayload.value = JSON.stringify([...cart.values()].map((line) => ({
      barang_id: line.barang_id,
      jumlah_terjual: line.jumlah_terjual
    })));
    updateCrossSell();
  };

  const crossSellContainer = document.getElementById('ai-cross-sell-container');
  const crossSellItems = document.getElementById('ai-cross-sell-items');

  const updateCrossSell = async () => {
    if (!crossSellContainer || !crossSellItems) return;
    const itemIds = [...cart.keys()];
    if (!itemIds.length) {
      crossSellContainer.style.display = 'none';
      return;
    }
    try {
      const res = await fetch('/ai/cross-sell', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify({ cart_item_ids: itemIds })
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data.suggestions && data.suggestions.length > 0) {
        crossSellItems.replaceChildren();
        for (const suggestion of data.suggestions) {
          const row = document.createElement('div');
          row.style.marginTop = '4px';
          const name = document.createElement('b');
          name.textContent = suggestion.nama_barang;
          const reason = document.createElement('span');
          reason.style.color = '#647974';
          reason.textContent = suggestion.alasan;
          row.append('\u{1F449} ', name, ' \u{2014} ', reason);
          crossSellItems.append(row);
        }
        crossSellContainer.style.display = 'block';
      } else {
        crossSellContainer.style.display = 'none';
      }
    } catch {
      crossSellContainer.style.display = 'none';
    }
  };

  addButton.addEventListener('click', () => {
    const item = matches.find((candidate) => String(candidate.id) === selectedId.value);
    const quantity = Number(quantityInput.value);
    if (!item) {
      input.setCustomValidity('Pilih barang dari daftar saran sebelum menambahkan.');
      input.reportValidity();
      return;
    }
    if (!Number.isSafeInteger(quantity) || quantity < 1) {
      quantityInput.reportValidity();
      return;
    }
    const existing = cart.get(item.id)?.jumlah_terjual || 0;
    if (existing + quantity > item.stok) {
      quantityInput.setCustomValidity(`Jumlah pada keranjang melebihi stok ${item.stok} unit.`);
      quantityInput.reportValidity();
      return;
    }
    quantityInput.setCustomValidity('');
    cart.set(item.id, {
      barang_id: item.id,
      nama_barang: item.nama_barang,
      jumlah_terjual: existing + quantity
    });
    renderCart();
    selectedId.value = '';
    input.value = '';
    details.hidden = true;
    status.textContent = `${item.nama_barang} ditambahkan ke keranjang.`;
    quantityInput.value = '1';
    closeList();
  });

  form.addEventListener('submit', (event) => {
    if (!cart.size) {
      event.preventDefault();
      addButton.focus();
      status.textContent = 'Tambahkan minimal satu barang sebelum menyimpan transaksi.';
    }
  });
  quantityInput.addEventListener('input', () => quantityInput.setCustomValidity(''));
  renderCart();
})();
