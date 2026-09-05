const currency = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });

export function money(value: number, signed = false): string {
  const prefix = signed && value > 0 ? '+' : '';
  return `${prefix}${value < 0 ? '-' : ''}$${currency.format(Math.abs(value))}`;
}

export function number(value: number): string {
  return decimal.format(value);
}

export function percent(value: number, signed = false): string {
  return `${signed && value > 0 ? '+' : ''}${decimal.format(value)}%`;
}

export function monthLabel(period: string): string {
  const [year, month] = period.split('-').map(Number);
  return new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric' }).format(
    new Date(year, month - 1, 1)
  );
}

const labels: Record<string, string> = {
  revenue: 'Revenue',
  cogs: 'COGS',
  traffic: 'More visitors',
  conversion: 'Buyer conversion',
  volume: 'More tickets',
  price: 'Prices changed',
  mix: 'What customers bought',
  items_per_order: 'Basket size',
  usage_efficiency: 'Ingredient usage',
  variable_labor: 'Flexible labor',
  fixed_labor: 'Labor cost',
  labor: 'Labor cost',
  rent: 'Rent',
  rent_cam: 'Rent + CAM',
  merchant_pos_fees: 'Merchant / POS fees',
  utilities: 'Utilities',
  insurance: 'Insurance',
  repairs_maintenance: 'Repairs & maintenance',
  cleaning_supplies: 'Cleaning / supplies',
  marketing: 'Marketing',
  software_admin: 'Software / accounting / admin',
  miscellaneous: 'Miscellaneous',
  rounding_adjustment: 'CSV rounding adjustment',
  electricity: 'Electricity',
  electricity_variable: 'Electricity use',
  electricity_fixed: 'Electricity base cost',
  other_variable: 'Other variable costs',
  other_fixed: 'Other fixed costs',
  everything_else: 'Everything else',
  'unit_cost.milk': 'Milk cost',
  'unit_cost.coffee_beans': 'Bean cost',
  'unit_cost.food': 'Food cost',
  'unit_cost.packaging': 'Packaging cost'
};

export function driverLabel(driver: string): string {
  return labels[driver] || driver.replaceAll('_', ' ').replaceAll('.', ' ');
}

export function findingSentence(driver: string, dollars: number): string {
  const label = driverLabel(driver);
  if (dollars < 0) return `${label} worked against profit`;
  return `${label} helped profit`;
}

export function headlineCopy(change: number): string {
  if (change < 0) return 'A harder month for profit.';
  if (change > 0) return 'Profit moved in the right direction.';
  return 'A quiet month.';
}
