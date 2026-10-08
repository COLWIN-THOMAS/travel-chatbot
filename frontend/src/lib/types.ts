export type Category = 'hotel' | 'restaurant' | 'attraction' | 'transport';
export type PlaceCategory = 'hotel' | 'restaurant' | 'attraction';

export interface User { id: string; email: string }
export interface TokenResponse { access_token: string; token_type: string; user: User }

export type TripPhase = 'undated' | 'upcoming' | 'ongoing' | 'completed';

export interface Trip {
  id: string;
  user_id: string;
  destination: string;
  budget_total: number;
  days_count: number;
  start_date: string | null; // YYYY-MM-DD; null = dates not decided
  end_date: string | null;
  phase: TripPhase;
  preferences: string[] | null;
  status: string;
  created_at: string;
}

/** A trip as listed in the history: the trip plus how it actually went. */
export interface TripSummary extends Trip {
  estimated_total: number;
  spend_total: number;
  items_total: number;
  items_visited: number;
}

export interface ItineraryItem {
  id: string;
  place_name: string;
  category: Category;
  estimated_cost: number;
  actual_cost: number;
  visited: boolean;
  order_in_day: number;
  notes: string | null;
}

export interface Day {
  id: string;
  day_number: number;
  date: string | null;
  estimated_total: number;
  spend_so_far: number;
  items: ItineraryItem[];
}

export interface Itinerary { days: Day[] }

export interface TrackerSummary {
  spend_total: number;
  budget_total: number;
  remaining: number;
  percent_used: number;
  items_total: number;
  items_visited: number;
  spent_by_category: Record<string, number>;
}

export interface Expense {
  id: string;
  amount: number;
  category: string | null;
  itinerary_item_id: string | null;
  logged_at: string | null;
}

export interface ItineraryNotice {
  rebalanced: boolean;
  message: string;
  days_from: number | null;
  days_to: number | null;
}

export interface VisitResult extends ItineraryItem { itinerary_notice: ItineraryNotice | null }

export interface ExpenseLogResponse {
  expense: Expense;
  spend_total: number;
  budget_remaining: number;
  itinerary_notice: ItineraryNotice | null;
}

export interface PlaceSummary {
  id: string;
  name: string;
  category: PlaceCategory;
  price_level: string | null;
  rating: number | null;
  address: string | null;
  lat: number | null;
  lon: number | null;
}

export interface Review { author_name: string | null; rating: number | null; text: string | null }

export interface PlaceDetail {
  id: string;
  name: string;
  address: string | null;
  lat: number | null;
  lon: number | null;
  rating: number | null;
  price_level: string | null;
  opening_hours: string[] | null;
  website: string | null;
  phone: string | null;
  description: string | null;
  photos: string[];
  reviews: Review[];
}

export interface DayForecast {
  day_number: number;
  date: string;
  temp_max: number;
  temp_min: number;
  condition: string;
  icon: 'sun' | 'partly' | 'cloud' | 'fog' | 'rain' | 'snow' | 'storm';
  precipitation_probability: number;
  advisory: string;
}
export interface Weather { destination: string; days: DayForecast[]; note: string | null }

export type ConversationState = 'GREETING' | 'COLLECTING' | 'CONFIRM' | 'GENERATE_PLAN' | 'POST_PLAN' | 'FALLBACK';

export interface Slots {
  destination?: string;
  budget_total?: number;
  days_count?: number;
  start_date?: string; // YYYY-MM-DD, or "undecided"
  preferences?: string[];
}

export interface ChatResponse {
  session_id: string;
  reply_text: string;
  conversation_state: ConversationState;
  extracted_fields: Slots;
  next_field: string | null;
  trip_id: string | null;
  itinerary: Itinerary | null;
  actions: string[];
}

export interface ChatMessage { role: 'user' | 'assistant'; content: string; created_at?: string | null; pending?: boolean }

export interface ChatHistory {
  session_id: string;
  state: ConversationState;
  slots: Slots;
  next_field: string | null;
  trip_id: string | null;
  messages: ChatMessage[];
}

export interface DeepLink { app_url: string | null; web_url: string; prefilled: boolean }
export interface RideLinks { uber: DeepLink; rapido: DeepLink }
