import { validationPlaceholder } from '@shared-validation';
import { utilsPlaceholder } from '@shared-utils';

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-4xl font-bold mb-4">Despens frontend placeholder</h1>
      <p className="text-xl">Validation: {validationPlaceholder()}</p>
      <p className="text-xl">Utils: {utilsPlaceholder()}</p>
    </div>
  );
}

