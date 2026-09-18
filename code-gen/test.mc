int duplo(int x) {
   return x + x;
}

int uvecaj(int y) {
   return duplo(y) + 1;
}

int main() {
   return uvecaj(5);
}