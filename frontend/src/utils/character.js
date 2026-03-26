export function getCharacterKey(character = {}) {
  return character?.id || character?.name || ''
}

export function matchesCharacter(candidate = {}, target = {}) {
  const targetId = String(target?.id || '').trim()
  return !!targetId && String(candidate?.id || '').trim() === targetId
}

export function findCharacterByRef(characters = [], target = {}) {
  return characters.find(character => matchesCharacter(character, target)) || null
}

export function findCharacterImageEntry(characterImages = {}, character = {}) {
  const key = String(character?.id || '').trim()
  if (key && characterImages[key]) {
    return characterImages[key]
  }
  return null
}
