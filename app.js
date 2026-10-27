const canvas = document.querySelector("#gameCanvas");
const context = canvas.getContext("2d");
const loadingStatus = document.querySelector("#loadingStatus");
const facingStatus = document.querySelector("#facingStatus");
const closetButton = document.querySelector("#closetButton");
const rotateButton = document.querySelector("#rotateButton");
const closetPanel = document.querySelector("#closetPanel");
const closetCloseButton = document.querySelector("#closetCloseButton");
const closetSaveButton = document.querySelector("#closetSaveButton");
const closetTabs = document.querySelector("#closetTabs");
const closetGrid = document.querySelector("#closetGrid");
const closetItemName = document.querySelector("#closetItemName");
const closetAvatarPreview = document.querySelector("#closetAvatarPreview");
const currentClothesGrid = document.querySelector("#currentClothesGrid");
const removeAllClothesButton = document.querySelector("#removeAllClothesButton");
const closetItemCount = document.querySelector("#closetItemCount");

const directions = ["front", "left", "back", "right"];
const directionAssetNames = ["front-right", "front-left", "back-left", "back-right"];
const baseImageSource = "assets/generated-game-assets/characters/base/brunette-character-base.png";
const baseDirectionSources = Object.fromEntries(
  directionAssetNames.map(direction => [
    direction,
    `assets/generated-game-assets/characters/directions/base/${direction}.png`
  ])
);
const categoryDefinitions = [
  { id: "new", label: "New" },
  { id: "tops", label: "Tops" },
  { id: "bottoms", label: "Bottoms" },
  { id: "shoes", label: "Shoes" },
  { id: "accessories", label: "Accessories" },
  { id: "goods", label: "Goods" },
  { id: "other", label: "Other" }
];

function createCatalogItems(category, count, filenamePrefix, namePrefix) {
  return Array.from({ length: count }, (_, index) => {
    const number = String(index + 1).padStart(2, "0");
    return {
      id: `${filenamePrefix}-${number}`,
      category,
      name: `${namePrefix} ${number}`,
      source: `assets/generated-game-assets/characters/clothing/${category}/${filenamePrefix}-${number}.png`
    };
  });
}

const wardrobeCatalog = {
  tops: createCatalogItems("tops", 28, "top", "Top"),
  bottoms: [],
  shoes: [],
  accessories: [],
  goods: [],
  other: []
};

wardrobeCatalog.new = wardrobeCatalog.tops.slice(0, 24);

const images = {};
const savedWardrobe = {
  tops: wardrobeCatalog.tops[0],
  bottoms: null,
  shoes: null,
  accessories: []
};
let draftWardrobe = cloneWardrobe(savedWardrobe);
let activeClosetCategory = "new";
const room = {
  centerX: 480,
  centerY: 310,
  radiusX: 315,
  radiusY: 176
};

const avatar = {
  x: 365,
  y: 383,
  targetX: 365,
  targetY: 383,
  facingIndex: 0,
  speed: 112,
  walking: false,
  walkPhase: 0
};

const pointerMarker = {
  x: 0,
  y: 0,
  opacity: 0
};

const furniture = [
  {
    depth: 296,
    collision: { x: 480, y: 304, radiusX: 82, radiusY: 38 },
    draw: drawTable
  },
  {
    depth: 358,
    collision: { x: 397, y: 354, radiusX: 31, radiusY: 22 },
    draw: () => drawChair(397, 350, false)
  },
  {
    depth: 363,
    collision: { x: 565, y: 357, radiusX: 31, radiusY: 22 },
    draw: () => drawChair(565, 353, true)
  }
];

let lastTimestamp = performance.now();
let ready = false;

function loadImage(source) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`Could not load ${source}`));
    image.src = source;
  });
}

function cloneWardrobe(wardrobe) {
  return {
    tops: wardrobe.tops,
    bottoms: wardrobe.bottoms,
    shoes: wardrobe.shoes,
    accessories: [...wardrobe.accessories]
  };
}

function wardrobeItems(wardrobe) {
  return [
    wardrobe.tops,
    wardrobe.bottoms,
    wardrobe.shoes,
    ...wardrobe.accessories
  ].filter(Boolean);
}

function directionalItemSource(item, direction) {
  if (item.category !== "tops") {
    return item.source;
  }
  return `assets/generated-game-assets/characters/directions/tops/${item.id}/${direction}.png`;
}

function wardrobeDirectionSources(wardrobe) {
  return wardrobeItems(wardrobe).flatMap(item =>
    directionAssetNames.map(direction => directionalItemSource(item, direction))
  );
}

async function ensureImage(source) {
  if (!images[source]) {
    images[source] = await loadImage(source);
  }
  return images[source];
}

async function loadAssets() {
  try {
    await Promise.all([
      ensureImage(baseImageSource),
      ...Object.values(baseDirectionSources).map(ensureImage),
      ...wardrobeDirectionSources(savedWardrobe).map(ensureImage)
    ]);
    ready = true;
    loadingStatus.hidden = true;
  } catch (error) {
    loadingStatus.textContent = error.message;
    loadingStatus.classList.add("error");
    throw error;
  }
}

function pointInRoom(x, y, margin = 0) {
  return (
    Math.abs(x - room.centerX) / (room.radiusX - margin) +
    Math.abs(y - room.centerY) / (room.radiusY - margin) <=
    1
  );
}

function pointHitsFurniture(x, y, padding = 0) {
  return furniture.some(item => {
    const collision = item.collision;
    const dx = (x - collision.x) / (collision.radiusX + padding);
    const dy = (y - collision.y) / (collision.radiusY + padding);
    return dx * dx + dy * dy <= 1;
  });
}

function canvasPoint(event) {
  const bounds = canvas.getBoundingClientRect();
  return {
    x: (event.clientX - bounds.left) * canvas.width / bounds.width,
    y: (event.clientY - bounds.top) * canvas.height / bounds.height
  };
}

function arrowPosition() {
  return {
    x: avatar.x,
    y: avatar.y - 139 + Math.sin(avatar.walkPhase) * 2
  };
}

function rotateAvatar() {
  avatar.facingIndex = (avatar.facingIndex + 1) % directions.length;
  avatar.targetX = avatar.x;
  avatar.targetY = avatar.y;
  avatar.walking = false;
  updateFacingStatus();
}

function updateFacingStatus() {
  const direction = directions[avatar.facingIndex];
  const clothing = wardrobeItems(savedWardrobe).map(item => item.name).join(", ");
  facingStatus.textContent = clothing
    ? `Facing ${direction} · ${clothing}`
    : `Facing ${direction} · Base clothes`;
}

function setDirectionFromMovement(dx, dy) {
  if (Math.abs(dx) > Math.abs(dy) * 1.35) {
    avatar.facingIndex = dx < 0 ? 1 : 3;
  } else {
    avatar.facingIndex = dy < 0 ? 2 : 0;
  }
  updateFacingStatus();
}

function handleCanvasClick(event) {
  if (!ready) {
    return;
  }

  const point = canvasPoint(event);
  const arrow = arrowPosition();
  if (Math.hypot(point.x - arrow.x, point.y - arrow.y) <= 22) {
    rotateAvatar();
    return;
  }

  if (!pointInRoom(point.x, point.y, 14)) {
    return;
  }

  avatar.targetX = point.x;
  avatar.targetY = point.y;
  pointerMarker.x = point.x;
  pointerMarker.y = point.y;
  pointerMarker.opacity = 1;
}

function update(delta) {
  const dx = avatar.targetX - avatar.x;
  const dy = avatar.targetY - avatar.y;
  const distance = Math.hypot(dx, dy);

  if (distance > 1.5) {
    const step = Math.min(avatar.speed * delta, distance);
    const nextX = avatar.x + dx / distance * step;
    const nextY = avatar.y + dy / distance * step;

    if (pointInRoom(nextX, nextY, 12) && !pointHitsFurniture(nextX, nextY, 12)) {
      if (!avatar.walking) {
        setDirectionFromMovement(dx, dy);
      }
      avatar.x = nextX;
      avatar.y = nextY;
      avatar.walking = true;
      avatar.walkPhase += delta * 12;
    } else {
      avatar.targetX = avatar.x;
      avatar.targetY = avatar.y;
      avatar.walking = false;
    }
  } else {
    avatar.x = avatar.targetX;
    avatar.y = avatar.targetY;
    avatar.walking = false;
  }

  pointerMarker.opacity = Math.max(0, pointerMarker.opacity - delta * 0.85);
}

function drawRoom() {
  context.fillStyle = "#656565";
  context.fillRect(0, 0, canvas.width, canvas.height);

  const top = [480, 134];
  const left = [165, 310];
  const right = [795, 310];
  const bottom = [480, 486];

  context.fillStyle = "#f5f5f3";
  context.beginPath();
  context.moveTo(top[0], 46);
  context.lineTo(left[0], 222);
  context.lineTo(left[0], left[1]);
  context.lineTo(top[0], top[1]);
  context.closePath();
  context.fill();

  context.fillStyle = "#ededeb";
  context.beginPath();
  context.moveTo(top[0], 46);
  context.lineTo(right[0], 222);
  context.lineTo(right[0], right[1]);
  context.lineTo(top[0], top[1]);
  context.closePath();
  context.fill();

  drawWindow();
  drawDoor();

  const floorGradient = context.createLinearGradient(260, 190, 700, 450);
  floorGradient.addColorStop(0, "#ead3aa");
  floorGradient.addColorStop(1, "#d3b181");
  context.fillStyle = floorGradient;
  context.beginPath();
  context.moveTo(...top);
  context.lineTo(...right);
  context.lineTo(...bottom);
  context.lineTo(...left);
  context.closePath();
  context.fill();

  context.save();
  context.beginPath();
  context.moveTo(...top);
  context.lineTo(...right);
  context.lineTo(...bottom);
  context.lineTo(...left);
  context.clip();
  context.strokeStyle = "#b9986c35";
  context.lineWidth = 2;
  for (let offset = -360; offset <= 360; offset += 20) {
    context.beginPath();
    context.moveTo(120 + offset, 245);
    context.lineTo(560 + offset, 492);
    context.stroke();
  }
  context.restore();

  context.strokeStyle = "#3b3c3c";
  context.lineWidth = 7;
  context.beginPath();
  context.moveTo(...left);
  context.lineTo(...top);
  context.lineTo(...right);
  context.stroke();
}

function drawWindow() {
  context.save();
  context.transform(1, -0.56, 0, 1, 0, 0);
  context.fillStyle = "#d9f4f3";
  context.fillRect(238, 298, 154, 75);
  context.strokeStyle = "#c4dddd";
  context.lineWidth = 4;
  context.strokeRect(238, 298, 154, 75);
  context.lineWidth = 2;
  for (let x = 276; x < 392; x += 38) {
    context.beginPath();
    context.moveTo(x, 298);
    context.lineTo(x, 373);
    context.stroke();
  }
  context.beginPath();
  context.moveTo(238, 336);
  context.lineTo(392, 336);
  context.stroke();
  context.restore();
}

function drawDoor() {
  context.save();
  context.transform(1, 0.56, 0, 1, 0, 0);
  context.fillStyle = "#fafafa";
  context.fillRect(678, -199, 54, 104);
  context.strokeStyle = "#c8c8c8";
  context.lineWidth = 4;
  context.strokeRect(678, -199, 54, 104);
  context.fillStyle = "#777";
  context.beginPath();
  context.arc(720, -132, 3, 0, Math.PI * 2);
  context.fill();
  context.restore();
}

function drawTable() {
  context.fillStyle = "#2d3030";
  context.fillRect(428, 299, 7, 83);
  context.fillRect(525, 299, 7, 83);
  context.fillStyle = "#f4f1e9";
  context.beginPath();
  context.moveTo(480, 246);
  context.lineTo(551, 286);
  context.lineTo(480, 326);
  context.lineTo(409, 286);
  context.closePath();
  context.fill();
  context.strokeStyle = "#cac4b9";
  context.lineWidth = 3;
  context.stroke();
}

function drawChair(x, y, flipped) {
  context.save();
  context.translate(x, y);
  if (flipped) {
    context.scale(-1, 1);
  }
  context.fillStyle = "#303337";
  context.beginPath();
  context.moveTo(-24, -49);
  context.lineTo(8, -33);
  context.lineTo(8, 10);
  context.lineTo(-24, -6);
  context.closePath();
  context.fill();
  context.fillRect(-20, 3, 6, 48);
  context.fillRect(7, 11, 5, 42);
  context.restore();
}

function drawPointerMarker() {
  if (pointerMarker.opacity <= 0) {
    return;
  }
  context.save();
  context.globalAlpha = pointerMarker.opacity;
  context.strokeStyle = "#ff7b18";
  context.lineWidth = 3;
  context.beginPath();
  context.ellipse(pointerMarker.x, pointerMarker.y, 14, 7, 0, 0, Math.PI * 2);
  context.stroke();
  context.restore();
}

function drawAvatar() {
  const direction = directionAssetNames[avatar.facingIndex];
  const bob = avatar.walking ? Math.sin(avatar.walkPhase) * 3 : 0;
  const sway = avatar.walking ? Math.sin(avatar.walkPhase * 0.5) * 0.025 : 0;
  const drawWidth = 112;
  const drawHeight = 126;

  context.save();
  context.translate(avatar.x - drawWidth / 2, avatar.y - drawHeight + bob);
  context.rotate(sway);

  context.drawImage(images[baseDirectionSources[direction]], 0, 0, drawWidth, drawHeight);
  for (const item of wardrobeItems(savedWardrobe)) {
    const source = directionalItemSource(item, direction);
    if (images[source]) {
      context.drawImage(images[source], 0, 0, drawWidth, drawHeight);
    }
  }
  context.restore();
}

function drawRotationArrow() {
  const arrow = arrowPosition();
  context.save();
  context.translate(arrow.x, arrow.y);
  context.fillStyle = "#ff7c12";
  context.strokeStyle = "#d95600";
  context.lineWidth = 2;
  context.beginPath();
  context.moveTo(0, 11);
  context.lineTo(-13, -2);
  context.quadraticCurveTo(0, -13, 13, -2);
  context.closePath();
  context.fill();
  context.stroke();
  context.restore();
}

function render() {
  drawRoom();
  drawPointerMarker();

  const renderables = furniture.map(item => ({
    depth: item.depth,
    draw: item.draw
  }));

  if (ready) {
    renderables.push({
      depth: avatar.y,
      draw: drawAvatar
    });
  }

  renderables.sort((a, b) => a.depth - b.depth);

  for (const item of renderables) {
    item.draw();
  }

  if (ready) {
    drawRotationArrow();
  }
}

function animate(timestamp) {
  const delta = Math.min((timestamp - lastTimestamp) / 1000, 0.04);
  lastTimestamp = timestamp;
  if (ready) {
    update(delta);
  }
  render();
  requestAnimationFrame(animate);
}

function isItemEquipped(item, wardrobe = draftWardrobe) {
  if (item.category === "accessories") {
    return wardrobe.accessories.some(accessory => accessory.id === item.id);
  }
  return wardrobe[item.category]?.id === item.id;
}

function removeDraftItem(item) {
  if (item.category === "accessories") {
    draftWardrobe.accessories = draftWardrobe.accessories.filter(
      accessory => accessory.id !== item.id
    );
  } else {
    draftWardrobe[item.category] = null;
  }
  renderCloset();
}

function selectDraftItem(item) {
  if (item.category === "accessories") {
    if (isItemEquipped(item)) {
      draftWardrobe.accessories = draftWardrobe.accessories.filter(
        accessory => accessory.id !== item.id
      );
    } else {
      draftWardrobe.accessories.push(item);
    }
  } else {
    draftWardrobe[item.category] = isItemEquipped(item) ? null : item;
  }
  renderCloset();
}

function createWardrobeImage(source, alt) {
  const image = document.createElement("img");
  image.src = source;
  image.alt = alt;
  image.draggable = false;
  return image;
}

function renderClosetTabs() {
  closetTabs.replaceChildren();
  for (const category of categoryDefinitions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "closet-tab";
    button.textContent = category.label;
    button.classList.toggle("active", category.id === activeClosetCategory);
    button.addEventListener("click", () => {
      activeClosetCategory = category.id;
      renderCloset();
    });
    closetTabs.append(button);
  }
}

function renderClosetGrid() {
  closetGrid.replaceChildren();
  const items = wardrobeCatalog[activeClosetCategory] ?? [];

  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "closet-empty";
    empty.textContent = "No items are available in this category yet.";
    closetGrid.append(empty);
    return;
  }

  for (const item of items) {
    const button = document.createElement("button");
    const equipped = isItemEquipped(item);
    button.type = "button";
    button.className = "closet-item";
    button.classList.toggle("equipped", equipped);
    button.title = item.name;
    button.append(createWardrobeImage(item.source, item.name));
    button.addEventListener("mouseenter", () => {
      closetItemName.textContent = item.name;
    });
    button.addEventListener("focus", () => {
      closetItemName.textContent = item.name;
    });
    button.addEventListener("click", () => selectDraftItem(item));

    if (equipped) {
      const label = document.createElement("span");
      label.className = "closet-item-label";
      label.textContent = "Equipped";
      button.append(label);
    }
    closetGrid.append(button);
  }
}

function renderClosetPreview() {
  closetAvatarPreview.replaceChildren();
  closetAvatarPreview.append(createWardrobeImage(baseImageSource, "Base character"));
  for (const item of wardrobeItems(draftWardrobe)) {
    closetAvatarPreview.append(createWardrobeImage(item.source, item.name));
  }
}

function renderCurrentClothes() {
  currentClothesGrid.replaceChildren();
  for (const item of wardrobeItems(draftWardrobe)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "current-clothes-item";
    button.title = `Remove ${item.name}`;
    button.append(createWardrobeImage(item.source, item.name));
    button.addEventListener("click", () => removeDraftItem(item));
    currentClothesGrid.append(button);
  }
}

function renderCloset() {
  renderClosetTabs();
  renderClosetGrid();
  renderClosetPreview();
  renderCurrentClothes();
  closetItemName.innerHTML = "&nbsp;";
  const totalItems = ["tops", "bottoms", "shoes", "accessories"]
    .reduce((total, category) => total + wardrobeCatalog[category].length, 0);
  closetItemCount.textContent = `item: ${totalItems} / 500`;
}

function openCloset() {
  draftWardrobe = cloneWardrobe(savedWardrobe);
  activeClosetCategory = "new";
  renderCloset();
  closetPanel.hidden = false;
}

function closeCloset() {
  closetPanel.hidden = true;
}

async function saveCloset() {
  closetSaveButton.disabled = true;
  closetSaveButton.textContent = "SAVING…";
  try {
    await Promise.all([
      ...wardrobeItems(draftWardrobe).map(item => ensureImage(item.source)),
      ...wardrobeDirectionSources(draftWardrobe).map(ensureImage)
    ]);
    Object.assign(savedWardrobe, cloneWardrobe(draftWardrobe));
    updateFacingStatus();
    closeCloset();
  } catch (error) {
    closetItemName.textContent = error.message;
  } finally {
    closetSaveButton.disabled = false;
    closetSaveButton.textContent = "SAVE";
  }
}

canvas.addEventListener("pointerdown", handleCanvasClick);
rotateButton.addEventListener("click", rotateAvatar);
closetButton.addEventListener("click", openCloset);
closetCloseButton.addEventListener("click", closeCloset);
closetSaveButton.addEventListener("click", saveCloset);
removeAllClothesButton.addEventListener("click", () => {
  draftWardrobe = {
    tops: null,
    bottoms: null,
    shoes: null,
    accessories: []
  };
  renderCloset();
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !closetPanel.hidden) {
    closeCloset();
  }
});

updateFacingStatus();
loadAssets();
requestAnimationFrame(animate);
