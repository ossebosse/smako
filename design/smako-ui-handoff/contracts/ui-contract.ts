/**
 * FÖRESLAGEN SEMANTISK UI-MODELL – INTE SMAKOS VERIFIERADE API.
 * Återanvänd befintliga typer där de finns. Identifierare, precision, enumvärden,
 * null/sentinel-hantering och fler fält måste mappas från verklig kod.
 * Filen kräver inte att produktionen byter till TypeScript.
 */
export type MealKind = "dinner" | "breakfast" | "snack";

/** null = ingen användarspecificerad gräns. 0 är ett explicit eget värde. */
export interface OptionalRange {
  min: number | null;
  max: number | null;
}

/** Bygg listan från verkligt schema; lås inte UI:t till fyra näringsämnen. */
export interface RangeFieldDefinition {
  key: string;
  label: string;
  unit: string;
  displayMin: number;
  displayMax: number;
  step: number;
  description?: string;
}

export interface MealSettingsView {
  kind: MealKind;
  enabled: boolean;
  count: number;
  portionsPerRecipe: number;
  distribution: {
    /** Kodnyckel från befintligt kostvals-schema. */
    dietId: string;
    /** null = Standard/planeraren väljer. 0 = explicit noll. */
    explicitCounts: Record<string, number | null>;
  };
  /** Uppskattad tillagad, ätbar vikt per portion, gram. */
  portionWeightGrams: OptionalRange;
  nutritionPerPortion: Record<string, OptionalRange>;
}

export type StoreScopeView =
  | { mode: "radius"; radiusKm: number }
  | { mode: "municipality"; municipalityId: string }
  | { mode: "manual"; storeIds: string[] };

export interface StoreOptionView {
  id: string;
  label: string;
  chainLabel?: string;
  /** null = saknad position/avstånd. Får aldrig visas som 0 km. */
  approximateDistanceKm: number | null;
  /** Visningsetikett härledd ur befintliga kanalfält. */
  priceChannelLabel: string;
  /** Okänt/datatäckning kommer från backend, inte gissat från kedjeloggan. */
  dataStatusLabel?: string;
}

export interface PreferenceView {
  likes: string[];
  dislikes: string[];
  excludedIngredients: string[];
  allergies: string[];
}

export interface ConfigurationView {
  postalCode: string;
  storeScope: StoreScopeView;
  /** Begränsning för gemensamma inköpskorgen, inte antal kandidater. */
  maxShoppingLocations: number;
  meals: Record<MealKind, MealSettingsView>;
  preferences: PreferenceView;
  /** Måste vara ett faktiskt stödt receptläge, inte bildens namn som ny API-enum. */
  dinnerRecipeModeId: string;
  /** 0–100 i UI:t. Adapter sköter eventuell annan verifierad representation. */
  minimumVerifiedOrganicCostPercent: number;
  requireOrganicAnimalProducts: boolean;
  surplusStrategyId: string;
}

/**
 * Beteendespecifikation, inte ett nytt obligatoriskt API-lager:
 * - Inläsning av befintlig konfiguration ska inte kasta bort ytterligare fält.
 * - Skrivning ska följa befintlig tillåtna-fält-/patchmodell, inte mass-assigna JSON.
 * - Avaktiverade måltider ska inte ge aktiva optimeringskrav.
 * - Persistens och utelämnande/null/sentinels följer det existerande kontraktet.
 */
export interface ExistingConfigurationAdapter<ExistingConfig, ExistingRequest> {
  hydrate(existing: ExistingConfig): ConfigurationView;
  serialize(view: ConfigurationView, previous: ExistingConfig): ExistingRequest;
}
