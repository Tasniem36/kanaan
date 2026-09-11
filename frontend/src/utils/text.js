// A manager types what is on the jar, or what a customer said down the phone — not
// what the database has. أ and ا are the same letter to them, so are ة and ه at the
// end of a word, and nobody types the shadda in فخّار. So the diacritics come off
// both sides before comparing, and every search box in the shop folds the same way:
// a product search and an order search that disagreed about ة would send a manager
// looking for a bug in the data.
//
// The diacritics are written as escapes, not as themselves: they are invisible
// combining marks, and a range spelled out literally here is one that any editor,
// diff or copy-paste can mangle without it showing.
const TASHKEEL = /[\u064B-\u0652\u0670]/g

export const foldArabic = (v) => String(v || '').toLowerCase()
  .replace(TASHKEEL, '')
  .replace(/[أإآ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه').trim()
