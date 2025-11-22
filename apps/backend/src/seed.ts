import { AppDataSource } from './data-source';

async function seed() {
  await AppDataSource.initialize();
  console.log('Seeding database...');
  // Seed logic here
  console.log('Database seeded!');
  await AppDataSource.destroy();
}

seed().catch((error) => {
  console.error('Error during seeding:', error);
  process.exit(1);
});

