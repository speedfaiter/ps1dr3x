CREATE TABLE IF NOT EXISTS kids (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kid_id TEXT NOT NULL REFERENCES kids(id),
  photo_path TEXT NOT NULL,
  eaten_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  hunger_level INTEGER,
  mood_before TEXT,
  is_food INTEGER,
  dish_name_he TEXT,
  dish_name_en TEXT,
  ingredients_json TEXT,
  estimated_grams INTEGER,
  traffic_light TEXT,
  energy_stars INTEGER,
  confidence TEXT,
  notes TEXT,
  ai_error TEXT
);

CREATE TABLE IF NOT EXISTS challenge_completions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kid_id TEXT NOT NULL REFERENCES kids(id),
  day_of_week INTEGER NOT NULL,
  completed_on DATE NOT NULL DEFAULT (date('now', 'localtime')),
  UNIQUE(kid_id, day_of_week, completed_on)
);

CREATE INDEX IF NOT EXISTS idx_meals_kid ON meals(kid_id, eaten_at DESC);
