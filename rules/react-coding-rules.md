# React Coding Rules

**Why this file exists:** React lets you write working code in many bad ways. These rules keep components small, state predictable, and re-renders under control — so the app stays cheap to change six months from now.

---

## 1. One component, one job

**Rule:** A component that fetches, transforms, and renders is three components glued together. Split it, or every change risks breaking the other two jobs.

**Bad**
```tsx
function UserPage() {
  const [users, setUsers] = useState([]);
  useEffect(() => { fetch('/api/users').then(r => r.json()).then(setUsers); }, []);
  return <ul>{users.filter(u => u.active).map(u => <li key={u.id}>{u.name}</li>)}</ul>;
}
```

**Good**
```tsx
function UserPage() {
  const users = useActiveUsers();      // fetching + filtering lives here
  return <UserList users={users} />;   // rendering only
}
```

**Self-check:** Can I describe this component in one sentence without using "and"?

---

## 2. Derive state, don't store it

**Rule:** Any value you can compute from existing state is not state. Storing it means two sources of truth that will drift apart.

**Bad**
```tsx
const [items, setItems] = useState([]);
const [total, setTotal] = useState(0);   // must be updated everywhere items changes
```

**Good**
```tsx
const [items, setItems] = useState([]);
const total = items.reduce((sum, i) => sum + i.price, 0);
```

**Self-check:** If I delete this state variable, can I still calculate it during render?

---

## 3. `useEffect` is for the outside world only

**Rule:** Effects are for syncing with things React doesn't control (network, timers, DOM APIs, subscriptions). Using them to compute data causes an extra render and a stale flash.

**Bad**
```tsx
const [fullName, setFullName] = useState('');
useEffect(() => { setFullName(`${first} ${last}`); }, [first, last]);
```

**Good**
```tsx
const fullName = `${first} ${last}`;
```

**Self-check:** Is this effect talking to something outside React? If no, delete it.

---

## 4. Never mutate state — replace it

**Rule:** React compares references. Mutating an object or array keeps the same reference, so the UI silently doesn't update.

**Bad**
```tsx
items.push(newItem);
setItems(items);
```

**Good**
```tsx
setItems([...items, newItem]);
```

**Self-check:** Did I create a new object/array, or change the old one?

---

## 5. Keys are IDs, never indexes

**Rule:** Index keys break when the list is reordered, filtered, or an item is removed — React reuses the wrong DOM node and input values jump to the wrong row.

**Bad**
```tsx
{users.map((u, i) => <Row key={i} user={u} />)}
```

**Good**
```tsx
{users.map(u => <Row key={u.id} user={u} />)}
```

**Self-check:** If I delete the first item, does every key still point to the same data?

---

## 6. Keep state as close to where it's used as possible

**Rule:** State lifted higher than needed re-renders the whole subtree on every keystroke. Only lift when two siblings genuinely share it.

**Bad**
```tsx
function App() {
  const [search, setSearch] = useState('');   // only SearchBox uses it
  return <><SearchBox value={search} onChange={setSearch} /><HugeDashboard /></>;
}
```

**Good**
```tsx
function App() {
  return <><SearchBox /><HugeDashboard /></>;  // search state lives inside SearchBox
}
```

**Self-check:** Which components actually read this state? Move it to their closest shared parent — no higher.

---

## 7. Reusable logic goes in a custom hook

**Rule:** Copy-pasted `useState` + `useEffect` blocks across components means every bug must be fixed in N places.

**Bad**
```tsx
// same 12 lines of fetch/loading/error logic in five components
```

**Good**
```tsx
function useUsers() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // ...
  return { data, loading };
}
```

**Self-check:** Have I written these hook lines somewhere else already?

---

## 8. Effects must clean up

**Rule:** Subscriptions, timers, and in-flight requests that outlive the component leak memory and set state on unmounted components.

**Bad**
```tsx
useEffect(() => { const id = setInterval(tick, 1000); }, []);
```

**Good**
```tsx
useEffect(() => {
  const id = setInterval(tick, 1000);
  return () => clearInterval(id);
}, []);
```

**Self-check:** Does this effect start something? Then it must return a function that stops it.

---

## 9. Props are a typed contract

**Rule:** `any` props and object bags hide breaking changes until runtime. Explicit props make wrong usage a compile error.

**Bad**
```tsx
function Card(props: any) { ... }
```

**Good**
```tsx
type CardProps = { title: string; onSelect: (id: string) => void };
function Card({ title, onSelect }: CardProps) { ... }
```

**Self-check:** Can I tell what this component needs without opening its body?

---

## 10. Fix re-renders by structure first, `memo` second

**Rule:** `memo`/`useMemo`/`useCallback` sprinkled everywhere adds cost and complexity while hiding the real problem — state in the wrong place or a fat context.

**Bad**
```tsx
// every component wrapped in memo, every handler in useCallback, still slow
```

**Good**
```tsx
// move state down (Rule 6), split the context, pass children as props — then measure
```

**Self-check:** Did I profile it, or am I guessing?

---

## 11. One context per concern

**Rule:** A single "AppContext" holding user + theme + cart re-renders every consumer when any one value changes.

**Bad**
```tsx
<AppContext.Provider value={{ user, theme, cart, setCart }}>
```

**Good**
```tsx
<UserContext.Provider value={user}>
  <CartContext.Provider value={cart}>
```

**Self-check:** Do all consumers of this context care about all of its values?

---

## 12. Conditional rendering, never conditional hooks

**Rule:** Hooks must run in the same order every render. An early return or an `if` above a hook crashes the component the moment the condition flips.

**Bad**
```tsx
if (!user) return null;
const [name, setName] = useState('');   // hook order changes
```

**Good**
```tsx
const [name, setName] = useState('');
if (!user) return null;
```

**Self-check:** Is every hook call above every `return`, and outside every `if`/loop?
